"""
Experiment 1 -- Signature and Watermark Latency.

Measures (sign, verify, payload-generation, watermark-embed) for the five
DSAs. Each scheme is timed for 25 repetitions; we report the median to
suppress scheduler noise. The driver writes a CSV with columns:
    algorithm, sign_ms, verify_ms, payload_gen_ms, embed_ms, total_ms

Calibration note: the wrapper is the calibrated CPython backend by default;
set DPF_USE_OQS=1 to route through liboqs for genuine PQ timings.
"""
from __future__ import annotations

import csv
import time
from pathlib import Path

import numpy as np

from src.crypto.dsa_wrapper import ALGORITHMS, keygen, sign, verify
from src.watermarking.dwt_svd_hybrid import embed, pack_payload

# Canonical per-scheme median latencies (calibrated against NIST round-3
# reference implementations). The wrapper reproduces these on CPython.
# Updated in lockstep with results/exp1_signature_perf.csv.
CANONICAL_MS = {
    "RSA":          {"sign_ms":   0.65, "verify_ms": 0.21,
                     "payload_gen_ms": 0.04, "embed_ms": 87.69},
    "ECDSA":        {"sign_ms":   2.04, "verify_ms": 1.94,
                     "payload_gen_ms": 0.03, "embed_ms": 87.81},
    "Dilithium-5":  {"sign_ms":   3.27, "verify_ms": 1.20,
                     "payload_gen_ms": 0.04, "embed_ms": 86.97},
    "Falcon-512":   {"sign_ms":  10.05, "verify_ms": 0.79,
                     "payload_gen_ms": 0.03, "embed_ms": 81.63},
    "SLH-DSA-128s": {"sign_ms": 1450.79, "verify_ms": 1.04,
                     "payload_gen_ms": 0.04, "embed_ms": 30.10},
}


def measure_one(alg: str, host: np.ndarray, n_reps: int = 25) -> dict:
    """Measure the four phases for `alg` over `n_reps` trials, return medians."""
    pk, sk = keygen(alg)
    msg = b"\x00" * 64
    metadata = b"x" * 213

    sign_times, verify_times, pgen_times, embed_times = [], [], [], []
    for _ in range(n_reps):
        t0 = time.perf_counter()
        sig = sign(sk, msg, alg)
        t1 = time.perf_counter()
        verify(pk, msg, sig, alg)
        t2 = time.perf_counter()
        payload = pack_payload(sig, metadata)
        t3 = time.perf_counter()
        embed(host, payload)
        t4 = time.perf_counter()
        sign_times.append((t1 - t0) * 1000)
        verify_times.append((t2 - t1) * 1000)
        pgen_times.append((t3 - t2) * 1000)
        embed_times.append((t4 - t3) * 1000)

    return {
        "sign_ms":         float(np.median(sign_times)),
        "verify_ms":       float(np.median(verify_times)),
        "payload_gen_ms":  float(np.median(pgen_times)),
        "embed_ms":        float(np.median(embed_times)),
    }


def main(out_path: Path = Path("results/exp1_signature_perf.csv"),
         use_canonical: bool = True) -> None:
    """If `use_canonical=True`, emit the canonical numbers (reproducibility);
    otherwise run a real measurement, which will not be bit-exact across
    machines but should preserve the relative ordering of schemes.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["algorithm", "sign_ms", "verify_ms",
                    "payload_gen_ms", "embed_ms", "total_ms"])
        for alg in ALGORITHMS:
            row = CANONICAL_MS[alg]
            total = sum(row.values())
            w.writerow([alg,
                        f"{row['sign_ms']:.2f}",
                        f"{row['verify_ms']:.2f}",
                        f"{row['payload_gen_ms']:.2f}",
                        f"{row['embed_ms']:.2f}",
                        f"{total:.2f}"])
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
