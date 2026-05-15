// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title  MediaRegistry
 * @notice On-chain provenance registry for the dpf framework.
 *         Supports both the per-item path of Alkhatib (2025)
 *         (registerMedia / setStatus) and the Merkle-batched path
 *         introduced by Yadav, Sheoran, Yadav (2026)
 *         (publishBatch / verifyInclusion).
 *
 *         The two paths are equivalent in cryptographic guarantee:
 *         any verifier with the off-chain (hash, signature, metadata)
 *         tuple can compute the leaf and verify against the on-chain
 *         root via short Merkle inclusion proofs.
 */
contract MediaRegistry {

    /* --------------------------------------------------------------------- */
    /*  Per-item path  (Scenario A of Alkhatib, 2025).                        */
    /* --------------------------------------------------------------------- */

    struct Record {
        bytes32 mediaHash;
        bytes   signature;
        bytes   metadata;
        bytes32 status;        // "authentic", "fake", "unknown"
        uint256 timestamp;
    }

    mapping(bytes32 => Record) public records;

    event MediaRegistered(bytes32 indexed mediaHash, address indexed registrant);
    event StatusUpdated   (bytes32 indexed mediaHash, bytes32 status);

    function registerMedia(
        bytes32 mediaHash,
        bytes calldata signature,
        bytes calldata metadata
    ) external {
        require(records[mediaHash].timestamp == 0, "already registered");
        records[mediaHash] = Record({
            mediaHash: mediaHash,
            signature: signature,
            metadata:  metadata,
            status:    bytes32("unknown"),
            timestamp: block.timestamp
        });
        emit MediaRegistered(mediaHash, msg.sender);
    }

    function setStatus(bytes32 mediaHash, bytes32 status) external {
        require(records[mediaHash].timestamp != 0, "not registered");
        records[mediaHash].status = status;
        emit StatusUpdated(mediaHash, status);
    }

    /* --------------------------------------------------------------------- */
    /*  Batched path  (Yadav, Sheoran, Yadav, 2026).                          */
    /* --------------------------------------------------------------------- */

    mapping(uint256 => bytes32) public batchRoots;   // batchId -> Merkle root
    uint256 public nextBatchId;

    event BatchPublished(uint256 indexed batchId, bytes32 root, uint256 nItems);

    function publishBatch(bytes32 root, uint256 nItems) external returns (uint256 batchId) {
        batchId = nextBatchId++;
        batchRoots[batchId] = root;
        emit BatchPublished(batchId, root, nItems);
    }

    /**
     * @notice Verify that ``leaf`` is included under ``batchRoots[batchId]``
     *         via the given Merkle inclusion ``proof``.
     */
    function verifyInclusion(
        uint256 batchId,
        bytes32 leaf,
        bytes32[] calldata proof
    ) external view returns (bool) {
        bytes32 hash = leaf;
        for (uint256 i = 0; i < proof.length; i++) {
            bytes32 sibling = proof[i];
            hash = hash < sibling
                ? keccak256(abi.encodePacked(hash, sibling))
                : keccak256(abi.encodePacked(sibling, hash));
        }
        return hash == batchRoots[batchId];
    }
}
