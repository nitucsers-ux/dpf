"""
Reproducibility tests: every row of every committed CSV must match what the
experiment driver produces on a fresh run. This is the core guarantee the
Data Availability statement makes.
"""
from __future__ import annotations

import csv
import tempfile
from pathlib import Path

import pytest

from experiments import (
    exp1_signature_perf,
    exp2_watermark_quality,
    exp3_resource_consumption,
    exp4_gas_cost,
    exp5_detection_accuracy,
)

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


def _read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@pytest.mark.parametrize("name,module", [
    ("exp1_signature_perf.csv",     exp1_signature_perf),
    ("exp2_watermark_quality.csv",  exp2_watermark_quality),
    ("exp3_resource_consumption.csv", exp3_resource_consumption),
    ("exp4_gas_cost.csv",           exp4_gas_cost),
    ("exp5_detection_accuracy.csv", exp5_detection_accuracy),
])
def test_csv_reproducibility(tmp_path, name, module):
    """Run the driver into a temp dir; assert it matches the committed CSV."""
    out_file = tmp_path / name
    module.main(out_path=out_file)
    expected = _read_csv(RESULTS_DIR / name)
    actual   = _read_csv(out_file)
    assert len(actual) == len(expected), f"row count mismatch for {name}"
    for i, (a, e) in enumerate(zip(actual, expected)):
        assert a == e, f"row {i} of {name} differs:\n  expected {e}\n  actual   {a}"
