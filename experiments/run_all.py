"""Master runner: execute experiments 1--5 in sequence.

Usage:
    python -m experiments.run_all

Each experiment script writes a CSV to results/. The pre-committed CSVs in
this repository are the canonical numbers reported in the paper; running the
experiments overwrites them with locally-reproduced values that should
match within numerical tolerance (defined in tests/test_reproducibility.py).
"""
from __future__ import annotations

import sys
import time
from importlib import import_module

EXPERIMENTS = [
    "experiments.exp1_signature_perf",
    "experiments.exp2_watermark_quality",
    "experiments.exp3_resource_consumption",
    "experiments.exp4_gas_cost",
    "experiments.exp5_detection_accuracy",
]


def main() -> int:
    overall_start = time.perf_counter()
    for name in EXPERIMENTS:
        print(f"\n=== Running {name} ===")
        t0 = time.perf_counter()
        try:
            mod = import_module(name)
            mod.main()
        except Exception as exc:  # noqa: BLE001
            print(f"  FAILED ({exc.__class__.__name__}): {exc}")
            return 1
        print(f"  done in {time.perf_counter() - t0:.2f}s")
    print(f"\nAll experiments completed in "
          f"{time.perf_counter() - overall_start:.1f}s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
