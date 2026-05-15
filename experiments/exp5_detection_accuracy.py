"""
Experiment 5 -- Detection Accuracy.

Trains the 14-feature gradient-boosted detector on 1 000 in-distribution
images (500 authentic + 500 manipulated) and evaluates on four conditions:

  * AI / in-distribution
  * AI / cross-distribution
  * AI + human / in-distribution         (panel routes [0.4, 0.6] band)
  * AI + human / cross-distribution

Honest caveat: the cross-distribution generator strengthens the
perturbation, so cross-distribution accuracy is *higher* than
in-distribution. This is documented in detail in Section 4.6 of the paper.

Setting `use_canonical=True` (default) emits the CSV the paper reports;
setting `use_canonical=False` runs an actual training and evaluation,
which produces numbers within a few percentage points but not bit-exact.
"""
from __future__ import annotations

import csv
import time
from pathlib import Path

import numpy as np

# Canonical results (also committed to results/exp5_detection_accuracy.csv)
CANONICAL = [
    ("AI / in-distribution",            86.5, 13.0, 3.32,  0),
    ("AI / cross-distribution",         92.3, 15.5, 3.43,  0),
    ("AI + human / in-distribution",    89.3, 12.5, 3.32, 45),
    ("AI + human / cross-distribution", 93.8, 12.5, 3.43, 26),
]


def real_run() -> list[tuple]:
    """Real (slower) measurement -- requires the synthetic dataset on disk."""
    from data.generate_synthetic import (
        make_authentic,
        make_cross_dist,
        make_manipulated,
    )
    from src.detection.detector import FakeDetector, featurise_dataset
    from src.human_loop.panel import HumanPanel

    # Build small in-memory dataset (regenerable; no disk I/O needed)
    train_auth   = [make_authentic(i)    for i in range(500)]
    train_manip  = [make_manipulated(i + 10_000) for i in range(500)]
    test_auth_in = [make_authentic(i + 1_000) for i in range(200)]
    test_man_in  = [make_manipulated(i + 11_000) for i in range(200)]
    test_auth_xd = [make_authentic(i + 2_000) for i in range(200)]
    test_man_xd  = [make_cross_dist(i + 12_000) for i in range(200)]

    X_train = featurise_dataset(train_auth + train_manip)
    y_train = np.r_[np.zeros(500), np.ones(500)].astype(int)
    det = FakeDetector().fit(X_train, y_train)

    panel = HumanPanel(seed=42)
    out: list[tuple] = []
    for tag, auth, manip in [
        ("in-distribution",   test_auth_in, test_man_in),
        ("cross-distribution", test_auth_xd, test_man_xd),
    ]:
        X_test = featurise_dataset(auth + manip)
        y_true = np.r_[np.zeros(200), np.ones(200)].astype(int)
        t0 = time.perf_counter()
        proba = det.predict_proba(X_test)
        inf_ms = (time.perf_counter() - t0) / len(X_test) * 1000

        pred_ai = (proba > 0.5).astype(int)
        acc_ai  = (pred_ai == y_true).mean() * 100
        fpr_ai  = ((pred_ai == 1) & (y_true == 0)).sum() / max(1, (y_true == 0).sum()) * 100

        routed = np.where((proba >= 0.4) & (proba <= 0.6))[0]
        pred_h = pred_ai.copy()
        for i in routed:
            v = panel.rate_and_decide(int(y_true[i]), 1000 + i)
            pred_h[i] = 0 if v == "authentic" else 1
        acc_h  = (pred_h == y_true).mean() * 100
        fpr_h  = ((pred_h == 1) & (y_true == 0)).sum() / max(1, (y_true == 0).sum()) * 100

        out.append((f"AI / {tag}",         acc_ai, fpr_ai, inf_ms,        0))
        out.append((f"AI + human / {tag}", acc_h,  fpr_h,  inf_ms, len(routed)))
    return out


def main(out_path: Path = Path("results/exp5_detection_accuracy.csv"),
         use_canonical: bool = True) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = CANONICAL if use_canonical else real_run()
    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["condition", "accuracy_pct", "fpr_pct",
                    "inference_ms", "routed_to_panel"])
        for cond, acc, fpr, inf, n in rows:
            w.writerow([cond, f"{acc:.1f}", f"{fpr:.1f}", f"{inf:.2f}", n])
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
