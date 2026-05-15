"""
End-to-end pipeline orchestrator.

Exposes two operating scenarios from Alkhatib (2025):

  * Scenario A -- publish():  a registered organisation creates, signs,
                              watermarks, AI-checks, and registers media on
                              chain (per-item or Merkle-batched).
  * Scenario B -- verify():   an end-user submits media for verification;
                              the framework runs signature verification,
                              then AI detection, then routes uncertain
                              items to the human panel.

The orchestrator is intentionally module-pluggable: each component
(crypto wrapper, watermark, registry, detector, panel, policy engine) is
injected via the constructor so a real production back-end (liboqs,
mainnet Ethereum, Xception ONNX, web review queue) can be substituted
without changing any pipeline code.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np

from src.blockchain.blockchain_sim import BlockchainSim
from src.crypto.dsa_wrapper import keygen, sign, verify
from src.detection.detector import FakeDetector, extract_features
from src.human_loop.panel import HumanPanel
from src.policy.engine import PolicyEngine, build_default_engine
from src.watermarking.dwt_svd_hybrid import (
    embed,
    extract,
    pack_payload,
    unpack_payload,
)
import hashlib as _hashlib


def _sha3(data: bytes) -> bytes:
    return _hashlib.sha3_256(data).digest()


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class PublishResult:
    media_id: bytes
    signature: bytes
    metadata: bytes
    watermarked: np.ndarray
    gas_cost: int
    on_chain: bool
    rejected_reason: Optional[str] = None


@dataclass
class VerifyResult:
    media_id: bytes
    verdict: str           # "authentic" | "fake" | "uncertain"
    signature_valid: Optional[bool]
    detector_score: Optional[float]
    panel_invoked: bool
    audit_events: list


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
class Pipeline:
    """Wires Modules 1-4 together; injectable backends for production."""

    def __init__(self,
                 algorithm: str = "Falcon-512",
                 detector: Optional[FakeDetector] = None,
                 panel: Optional[HumanPanel] = None,
                 registry: Optional[BlockchainSim] = None,
                 policy: Optional[PolicyEngine] = None) -> None:
        self.algorithm = algorithm
        self.detector  = detector  or FakeDetector()
        self.panel     = panel     or HumanPanel()
        self.registry  = registry  or BlockchainSim()
        self.policy    = policy    or build_default_engine()
        # Trusted-creator keypair (in production, kept in an HSM)
        self.pk, self.sk = keygen(algorithm)

    # -------- Scenario A: publish (registered organisation) ----------------
    def publish(self,
                image: np.ndarray,
                metadata: Dict[str, Any],
                creator_id: bytes = b"creator0") -> PublishResult:
        # 1. Hash image+metadata
        meta_bytes = json.dumps(metadata, sort_keys=True).encode()
        media_id   = _sha3(image.tobytes() + meta_bytes)

        # 2. Sign
        signature  = sign(self.sk, media_id, self.algorithm)

        # 3. Embed watermark
        payload = pack_payload(signature, meta_bytes)
        watermarked = embed(image, payload)

        # 4. AI safety pre-check (publishing a known-fake is forbidden)
        features = extract_features(watermarked).reshape(1, -1)
        if hasattr(self.detector.clf, "estimators_"):
            score = float(self.detector.predict_proba(features)[0])
        else:
            score = 0.0  # detector not trained yet, skip safety check
        if score > 0.6:
            self.policy.evaluate({
                "event": "publish-rejected",
                "media_id": media_id.hex(),
                "detector_score": score,
            })
            return PublishResult(media_id, signature, meta_bytes, watermarked,
                                 gas_cost=0, on_chain=False,
                                 rejected_reason="detector flagged as fake")

        # 5. Register on chain
        receipt = self.registry.register_media(media_id, signature, meta_bytes)
        status_receipt = self.registry.set_status(media_id, "authentic")
        gas_cost = receipt.total + status_receipt.total
        self.policy.evaluate({
            "event": "publish-ok",
            "media_id": media_id.hex(),
            "gas_cost": gas_cost,
            "signature_valid": True,
        })
        return PublishResult(media_id, signature, meta_bytes, watermarked,
                             gas_cost=gas_cost, on_chain=True)

    # -------- Scenario B: verify (end-user) --------------------------------
    def verify(self,
               watermarked: np.ndarray,
               metadata: Dict[str, Any]) -> VerifyResult:
        meta_bytes = json.dumps(metadata, sort_keys=True).encode()
        media_id   = _sha3(watermarked.tobytes() + meta_bytes)

        # 1. Extract watermark, recover signature
        # Standard 213 B metadata + 666 B Falcon sig + 12 B framing = 891 B
        try:
            blob = extract(watermarked, n_bytes=12 + 666 + len(meta_bytes))
            body, _ = unpack_payload(blob)
            sig = body[:666]
            sig_valid = verify(self.pk, media_id, sig, self.algorithm)
        except (ValueError, Exception):
            sig_valid = False

        # 2. AI detection
        features = extract_features(watermarked).reshape(1, -1)
        if hasattr(self.detector.clf, "estimators_"):
            score = float(self.detector.predict_proba(features)[0])
        else:
            score = 0.5

        # 3. Route to human panel if uncertain
        panel_invoked = False
        if 0.4 <= score <= 0.6:
            panel_invoked = True
            ratings = self.panel.rate_one(true_label=1 if score >= 0.5 else 0,
                                          item_seed=int.from_bytes(media_id[:4],
                                                                    "big"))
            verdict = self.panel.verdict(ratings)
        else:
            verdict = "authentic" if score < 0.5 else "fake"

        # 4. Policy fire
        events = self.policy.evaluate({
            "media_id": media_id.hex(),
            "signature_valid": sig_valid,
            "detector_score": score,
            "panel_invoked": panel_invoked,
            "verdict": verdict,
        })

        return VerifyResult(media_id, verdict, sig_valid, score,
                            panel_invoked, [e.to_dict() for e in events])


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main() -> None:  # pragma: no cover -- thin CLI demo
    import argparse
    parser = argparse.ArgumentParser(
        description="dpf pipeline CLI (Scenario A: publish, Scenario B: verify)"
    )
    parser.add_argument("scenario", choices=["publish", "verify"])
    parser.add_argument("--algorithm", default="Falcon-512")
    args = parser.parse_args()
    pipeline = Pipeline(algorithm=args.algorithm)
    print(f"dpf pipeline ready ({args.algorithm}); scenario = {args.scenario}.")
    print("This CLI is a thin demo; programmatic API is in src.pipeline.")


if __name__ == "__main__":
    main()
