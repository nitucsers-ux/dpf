"""
Experiment 3 -- Resource Consumption.

For each DSA, measure the bytes of signature + 213-byte metadata template +
12-byte DPF1 framing header. These sizes are FIPS-mandated for the PQ
schemes (and bounded for RSA-2048-PSS / ECDSA-P521), so the experiment is
fully deterministic.
"""
from __future__ import annotations

import csv
from pathlib import Path

from src.crypto.dsa_wrapper import ALGORITHMS


METADATA_BYTES = 213
HEADER_BYTES   = 12


def main(out_path: Path = Path("results/exp3_resource_consumption.csv")) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["algorithm", "signature_bytes", "metadata_bytes",
                    "header_bytes", "total_bytes", "kilobytes"])
        for alg, spec in ALGORITHMS.items():
            total = spec.sig_size + METADATA_BYTES + HEADER_BYTES
            w.writerow([alg, spec.sig_size, METADATA_BYTES, HEADER_BYTES,
                        total, f"{total/1024:.2f}"])
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
