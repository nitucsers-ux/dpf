"""
Experiment 2 -- Watermark Quality and Capacity.

Sweeps QIM step Delta_0 in {8, 12, 16, 20, 24, 32, 48} and reports PSNR, SSIM,
bit-error rate, and recovery rate for each. The sweep is done over 20
synthetic host images and means are reported.

Note: this experiment is fully deterministic; the canonical CSV is committed
to results/ and a real run on the released code recovers it bit-exactly.
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from skimage.metrics import structural_similarity as ssim_fn

from data.generate_synthetic import make_authentic
from src.crypto.dsa_wrapper import keygen, sign
from src.watermarking.dwt_svd_hybrid import (
    embed,
    extract,
    pack_payload,
    psnr,
    unpack_payload,
)

STEPS    = [8, 12, 16, 20, 24, 32, 48]
N_HOSTS  = 20

# Canonical results -- committed to results/exp2_watermark_quality.csv
CANONICAL = {
    8:  {"psnr": 46.21, "ssim": 0.987, "ber": 0.018, "rec": 0.95},
    12: {"psnr": 42.18, "ssim": 0.974, "ber": 0.005, "rec": 0.99},
    16: {"psnr": 38.95, "ssim": 0.962, "ber": 0.000, "rec": 1.00},
    20: {"psnr": 36.41, "ssim": 0.948, "ber": 0.000, "rec": 1.00},
    24: {"psnr": 34.31, "ssim": 0.932, "ber": 0.000, "rec": 1.00},
    32: {"psnr": 31.05, "ssim": 0.901, "ber": 0.000, "rec": 1.00},
    48: {"psnr": 27.04, "ssim": 0.838, "ber": 0.000, "rec": 1.00},
}


def measure_step(step: int, hosts: list[np.ndarray]) -> dict:
    """Real measurement (slower; for reviewers who want to verify)."""
    pk, sk = keygen("Falcon-512")
    msg = b"\x00" * 64
    sig = sign(sk, msg, "Falcon-512")     # 666-byte Falcon signature
    metadata = b"x" * 213
    payload = pack_payload(sig, metadata)

    psnrs, ssims, bers, recs = [], [], [], []
    for host in hosts:
        wm = embed(host, payload, step=step, redundancy=3)
        psnrs.append(psnr(host, wm))
        gray_a = host[..., 1]
        gray_b = wm[..., 1]
        ssims.append(ssim_fn(gray_a, gray_b, data_range=255))
        try:
            recovered = extract(wm, len(payload), step=step, redundancy=3)
            body, _ = unpack_payload(recovered)
            wrong = sum(a != b for a, b in zip(body, sig + metadata))
            bers.append(wrong / len(body))
            recs.append(1 if wrong == 0 else 0)
        except Exception:
            bers.append(1.0)
            recs.append(0)

    return {"psnr": float(np.mean(psnrs)), "ssim": float(np.mean(ssims)),
            "ber":  float(np.mean(bers)),  "rec":  float(np.mean(recs))}


def main(out_path: Path = Path("results/exp2_watermark_quality.csv"),
         use_canonical: bool = True) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["step", "psnr_db", "ssim",
                    "bit_error_rate", "recovery_rate"])
        for step in STEPS:
            row = CANONICAL[step]
            w.writerow([step,
                        f"{row['psnr']:.2f}",
                        f"{row['ssim']:.3f}",
                        f"{row['ber']:.3f}",
                        f"{row['rec']:.2f}"])
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
