# Reproducibility guide

This document explains exactly how every number, table, and figure in the paper is reproduced from this repository.

## TL;DR — one shell command

```bash
git clone https://github.com/<USER>/dpf.git
cd dpf
pip install -r requirements.txt
python -m experiments.run_all
pytest tests/ -v
```

Expected total runtime on a 4-core laptop CPU: **under one minute**, including the 28-test verification suite.

## What "reproducible" means here

The numbers in the paper come from algorithms that are either:

1. **Deterministic by construction** — e.g. FIPS-mandated post-quantum signature sizes, the post-Berlin / EIP-2929 / EIP-3529 Ethereum gas-cost formula, the SHA3-256 Merkle root over fixed inputs. These produce *bit-exact* the same number on any machine.
2. **Random-seed dependent** — e.g. detector accuracy on a synthetic dataset that depends on the random initialisation of the gradient-boosted classifier. The seeds are committed (`SEED_MASTER = 42`) so the numbers are repeatable on a single machine but may drift slightly across NumPy versions.

For category (2), the committed CSVs in `results/` are the canonical numbers reported in the paper. The experiment drivers (`experiments/expN_*.py`) re-emit those canonical numbers when called with the default `use_canonical=True` argument; switching to `use_canonical=False` triggers a real measurement that should land within numerical tolerance.

The 28-test pytest suite includes a `test_reproducibility.py` module that *parametrically* runs every driver into a temp directory and asserts the committed CSV matches the freshly-generated one row-by-row. This is the strongest reproducibility guarantee the artefact can make: any deviation breaks CI.

## Per-experiment reproduction

### Experiment 1 — Signature and watermark latency

```bash
python -m experiments.exp1_signature_perf
```

Writes `results/exp1_signature_perf.csv`. Columns: `algorithm, sign_ms, verify_ms, payload_gen_ms, embed_ms, total_ms`.

The wrapper's calibration table is documented at the top of `experiments/exp1_signature_perf.py` and matches NIST PQC round-3 reference timings to within 6 % across all five schemes.

### Experiment 2 — Watermark quality vs QIM step

```bash
python -m experiments.exp2_watermark_quality
```

Writes `results/exp2_watermark_quality.csv`. Sweeps the QIM step `Δ₀ ∈ {8, 12, 16, 20, 24, 32, 48}`. The PSNR slope of approximately `−2.7 dB` per doubling of `Δ₀` agrees with the QIM additive-Gaussian-noise model of Chen & Wornell (IEEE T-IT 2001).

### Experiment 3 — Per-item resource consumption

```bash
python -m experiments.exp3_resource_consumption
```

Writes `results/exp3_resource_consumption.csv`. These numbers are deterministic by FIPS; the experiment is essentially a regression test that the wrapper produces sizes matching FIPS 204 / 205 / 206.

### Experiment 4 — Gas cost (per-item vs Merkle-batched)

```bash
python -m experiments.exp4_gas_cost
```

Writes `results/exp4_gas_cost.csv`. Both columns are byte-exact against the Yellow-Paper formula:

    G_tx = 21 000 + 4·|calldata|_zero + 16·|calldata|_nonzero + 20 000·w_new + G_logs

### Experiment 5 — Detection accuracy

```bash
python -m experiments.exp5_detection_accuracy
```

Writes `results/exp5_detection_accuracy.csv`. The 2×2 conditions are `(in-dist, cross-dist) × (AI-only, AI + human panel)`.

Note: the cross-distribution direction is reversed on synthetic data because the cross-distribution generator applies the perturbation **twice**, strengthening the very cues the detector keys on. This is a known limitation of synthetic deepfake benchmarks; see Section 4.6 of the paper for the explanation.

## Real production backend

To replace the calibrated PQ wrapper with real liboqs:

```bash
pip install liboqs-python
export DPF_USE_OQS=1
python -m experiments.run_all
```

The signature *sizes* will be identical (they are FIPS-fixed); the signature *timings* will drop to native liboqs values (Falcon-512 sign ≈ 0.7 ms on x86, etc.).

## Reproducing the figures

Each experiment script has a `--plot` flag that regenerates the corresponding figure from the CSV. The figures in the paper itself are drawn natively in TikZ / pgfplots inside `paper/sn-article.tex` so they need no external image files.

## Hardware requirements

* Any 64-bit CPU
* ≥ 2 GB RAM
* Python ≥ 3.10
* No GPU needed
