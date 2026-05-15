"""Gas-accurate Ethereum simulator.

Implements the Yellow-Paper gas formula at post-Berlin / EIP-2929 /
EIP-3529 prices:

    G_tx = 21_000
         +  4 * |calldata|_{=0}      (zero-byte calldata)
         + 16 * |calldata|_{!=0}     (non-zero-byte calldata)
         + 20_000 * w_new            (each fresh 32-byte storage slot)
         + G_logs                    (LOGn gas per emitted event)

The simulator never broadcasts transactions; it accounts gas only.
This is sufficient to reproduce every cost figure in the paper. To
target a real Ethereum back-end, swap this module for a ``web3.py``
client — the function signatures are deliberately compatible.

References
----------
- Buterin, V. (2014). Ethereum white paper.   [bib9]
- Wood, G. (2024). Ethereum Yellow Paper, post-Berlin schedule.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

# Gas schedule (post-Berlin).
G_TRANSACTION       = 21_000
G_CALLDATA_ZERO     =      4
G_CALLDATA_NONZERO  =     16
G_SSTORE_NEW        = 20_000
G_LOG_BASE          =    375  # base cost of LOGn
G_LOG_PER_TOPIC     =    375
G_LOG_PER_DATA_BYTE =      8


def gas_calldata(calldata: bytes) -> int:
    """Gas charged for transmitting ``calldata`` (Berlin-era pricing)."""
    n_zero    = calldata.count(b"\x00")
    n_nonzero = len(calldata) - n_zero
    return n_zero * G_CALLDATA_ZERO + n_nonzero * G_CALLDATA_NONZERO


def gas_sstore_new(n_words: int) -> int:
    """Gas charged for ``n_words`` brand-new 32-byte storage writes."""
    return n_words * G_SSTORE_NEW


def gas_log(topics: int, data_len: int) -> int:
    """Gas charged for a LOGn event with ``topics`` topics and ``data_len`` bytes."""
    return G_LOG_BASE + topics * G_LOG_PER_TOPIC + data_len * G_LOG_PER_DATA_BYTE


def storage_words(payload_bytes: int) -> int:
    """Number of 32-byte storage slots required to hold ``payload_bytes``."""
    return (payload_bytes + 31) // 32


@dataclass
class GasReceipt:
    """A receipt describing the gas accounted for a transaction."""
    transaction:     str
    base_gas:        int
    calldata_gas:    int
    storage_gas:     int
    logs_gas:        int

    @property
    def total(self) -> int:
        return self.base_gas + self.calldata_gas + self.storage_gas + self.logs_gas


@dataclass
class MediaRegistryRecord:
    """A single per-item registration record (Scenario A, source-paper layout)."""
    media_hash: bytes
    signature:  bytes
    metadata:   bytes
    status:     str = "unknown"


@dataclass
class BatchRegistryRecord:
    """A single Merkle-batched registration record (this paper's contribution)."""
    merkle_root: bytes
    n_items:     int
    batch_id:    int


@dataclass
class BlockchainSim:
    """In-memory gas-accurate Ethereum simulator with both per-item and batched paths."""

    per_item_records: list[MediaRegistryRecord] = field(default_factory=list)
    batches:          list[BatchRegistryRecord] = field(default_factory=list)

    # ----- per-item path (source-paper layout) -----------------------------

    def register_media(self, media_hash: bytes, signature: bytes, metadata: bytes) -> GasReceipt:
        """Register a single (hash, signature, metadata) tuple on-chain."""
        calldata = media_hash + signature + metadata
        record = MediaRegistryRecord(
            media_hash=media_hash, signature=signature, metadata=metadata
        )
        self.per_item_records.append(record)
        # On-chain we write: 32-byte hash + signature + metadata, all fresh.
        storage_bytes = len(media_hash) + len(signature) + len(metadata)
        return GasReceipt(
            transaction  = "registerMedia",
            base_gas     = G_TRANSACTION,
            calldata_gas = gas_calldata(calldata),
            storage_gas  = gas_sstore_new(storage_words(storage_bytes)),
            logs_gas     = gas_log(topics=2, data_len=32),
        )

    def set_status(self, media_hash: bytes, status: str) -> GasReceipt:
        """Update the status of a previously-registered record."""
        # Locate and mutate (no gas cost for emulator, but we account it).
        for record in self.per_item_records:
            if record.media_hash == media_hash:
                record.status = status
                break
        else:
            raise KeyError("media_hash not found")
        return GasReceipt(
            transaction  = "setStatus",
            base_gas     = G_TRANSACTION,
            calldata_gas = gas_calldata(media_hash + status.encode()),
            storage_gas  = G_SSTORE_NEW // 4,  # status reuses a slot (no fresh write)
            logs_gas     = gas_log(topics=2, data_len=32),
        )

    # ----- batched path (this paper's contribution) ------------------------

    def publish_batch(self, leaves: list[bytes]) -> tuple[GasReceipt, bytes]:
        """Anchor a batch of ``len(leaves)`` items in a single 32-byte Merkle root.

        Returns
        -------
        (GasReceipt, bytes)
            The gas receipt and the on-chain Merkle root.
        """
        root = self._merkle_root(leaves)
        batch_id = len(self.batches)
        self.batches.append(
            BatchRegistryRecord(merkle_root=root, n_items=len(leaves), batch_id=batch_id)
        )
        # Calldata is just the 32-byte root.
        calldata = root
        receipt = GasReceipt(
            transaction  = "publishBatch",
            base_gas     = G_TRANSACTION,
            calldata_gas = gas_calldata(calldata),
            storage_gas  = gas_sstore_new(1),   # only one fresh slot
            logs_gas     = gas_log(topics=2, data_len=32),
        )
        return receipt, root

    def verify_inclusion(self, root: bytes, leaf: bytes, proof: list[bytes]) -> bool:
        """Verify a Merkle inclusion proof against the given root."""
        h = leaf
        for sibling in proof:
            h = (
                hashlib.sha3_256(h + sibling).digest()
                if h < sibling
                else hashlib.sha3_256(sibling + h).digest()
            )
        return h == root

    # ----- helpers ---------------------------------------------------------

    @staticmethod
    def _merkle_root(leaves: list[bytes]) -> bytes:
        """Compute the SHA3-256 Merkle root of ``leaves``."""
        if not leaves:
            return b"\x00" * 32
        nodes = list(leaves)
        while len(nodes) > 1:
            if len(nodes) % 2 != 0:
                nodes.append(nodes[-1])  # duplicate last for odd batches
            nxt = []
            for i in range(0, len(nodes), 2):
                a, b = nodes[i], nodes[i + 1]
                pair = a + b if a < b else b + a
                nxt.append(hashlib.sha3_256(pair).digest())
            nodes = nxt
        return nodes[0]


# ---------------------------------------------------------------------------
# Convenience: amortised per-item gas for a Merkle batch of size N.
# ---------------------------------------------------------------------------

def amortised_batch_gas(n: int, signature_size: int = 666, metadata_size: int = 213) -> float:
    """Compute the amortised per-item gas of a Merkle-batched registration.

    Each leaf is SHA3-256(media_hash || signature || metadata), so the
    on-chain footprint is independent of ``signature_size`` once the
    batch is committed. Only one storage word is written for the root.
    """
    leaves = [b"\x00" * 32] * n  # placeholder, hashing identical bytes
    sim = BlockchainSim()
    receipt, _ = sim.publish_batch(leaves)
    return receipt.total / n
