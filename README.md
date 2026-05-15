# dpf — A Reproducible Implementation of a Multifaceted Deepfake Prevention Framework

[![CI](https://github.com/USER/dpf/actions/workflows/ci.yml/badge.svg)](https://github.com/USER/dpf/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.PLACEHOLDER.svg)](https://doi.org/10.5281/zenodo.PLACEHOLDER)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

This repository is the companion artefact for the paper

> **Implementation and Evaluation of a Multifaceted Deepfake Prevention Framework**
> Nitu Yadav, Savita Sheoran, Deepak Yadav
> Department of Computer Science & Engineering, Indira Gandhi University, Meerpur, Rewari
> *(under review, 2026)*

The paper extends Alkhatib's multifaceted prevention framework with an end-to-end executable implementation, a Merkle-batched on-chain layout, a calibrated post-quantum signature wrapper, and a cross-distribution evaluation harness. This repository contains the complete source code, synthetic dataset generator, experiment drivers, raw CSV results, a Solidity smart contract, unit tests, and the LaTeX manuscript sources.

---

## Quick start

The single command below regenerates **every table and figure** in the paper:

```bash
git clone https://github.com/USER/dpf.git
cd dpf
pip install -r requirements.txt
python -m experiments.run_all
pytest tests/ -v
```

Expected runtime on a modern laptop: approximately 90 seconds end-to-end. No GPU, no external dataset download, no liboqs build required.

---

## Repository layout

```
dpf/
├── README.md                          # this file
├── LICENSE                            # MIT
├── CITATION.cff                       # how to cite this work
├── requirements.txt                   # Python dependencies
├── pyproject.toml                     # package metadata
├── .github/workflows/ci.yml           # GitHub Actions CI
│
├── src/                               # framework source (~3,100 lines)
│   ├── pipeline.py                    # end-to-end orchestrator (Publish + Verify)
│   ├── crypto/
│   │   └── pq_wrapper.py              # calibrated post-quantum signature wrapper
│   ├── watermarking/
│   │   └── dwt_svd_hybrid.py          # hybrid DWT-SVD QIM embedder/extractor
│   ├── blockchain/
│   │   ├── blockchain_sim.py          # gas-accurate Ethereum simulator
│   │   └── MediaRegistry.sol          # Solidity smart contract (per-item + batched)
│   ├── detection/
│   │   └── detector.py                # feature-engineered deepfake detector
│   ├── human_loop/
│   │   └── panel.py                   # 10-expert simulated Likert panel
│   └── governance/
│       └── policy_engine.py           # policy/incident engine
│
├── data/
│   ├── generate_synthetic.py          # deterministic synthetic-image generator
│   └── README.md                      # dataset documentation
│
├── experiments/
│   ├── run_all.py                     # master driver — regenerates everything
│   ├── exp1_signature_perf.py         # signature & watermark latency
│   ├── exp2_watermark_quality.py      # watermark imperceptibility / capacity
│   ├── exp3_resource_consumption.py   # per-item RAM footprint
│   ├── exp4_gas_cost.py               # per-item vs Merkle-batched gas
│   └── exp5_detection_accuracy.py     # detection accuracy (in-dist + cross-dist)
│
├── results/                           # raw CSV outputs (committed to repo)
│   ├── exp1_signature_perf.csv
│   ├── exp2_watermark_quality.csv
│   ├── exp3_resource_consumption.csv
│   ├── exp4_gas_cost.csv
│   ├── exp5_detection_accuracy.csv
│   └── README.md
│
├── tests/                             # pytest suite (23 tests)
│   ├── test_pipeline.py
│   ├── test_reproducibility.py
│   ├── test_crypto.py
│   ├── test_watermark.py
│   ├── test_blockchain.py
│   └── test_detector.py
│
└── paper/                             # manuscript sources
    ├── dpf-paper.tex                  # main manuscript
    ├── dpf-supplementary.tex          # supplementary information
    ├── sn-bibliography.bib            # shared bibliography
    └── README.md
```

---

## What this artefact contributes

The paper identifies three gaps in the reference framework (Alkhatib, 2025) and addresses each one with measurable contributions:

| Gap | Contribution in this repo |
|---|---|
| **Reproducibility** — the source paper presents tables of algorithmic constants but does not release the code that produced them | An MIT-licensed end-to-end implementation of all four framework modules. Every numeric value in the paper is recomputed by `python -m experiments.run_all`. |
| **Storage** — per-item on-chain footprint scales linearly with signature size; for SLH-DSA this is $5.2{\times}10^6$ gas per item | A Merkle-batched on-chain layout (see `src/blockchain/MediaRegistry.sol`) that anchors a batch of $N$ items in a single 32-byte root, amortising to $\approx 324$ gas per item at $N=256$ — a ratio of $\approx 1{,}795\times$. |
| **Generalisation** — the source paper acknowledges cross-dataset accuracy loss but does not measure it | A cross-distribution evaluation harness (`exp5_detection_accuracy.py`) that quantifies the in-distribution / out-of-distribution accuracy delta and reports the human-in-the-loop boost separately. |

---

## Headline numbers

All numbers are reproduced by `python -m experiments.run_all` from the deterministic seeds in `data/generate_synthetic.py`.

| Metric | Value | Source experiment |
|---|---|---|
| Lowest combined latency among PQ schemes | 92.5 ms (Falcon-512) | Exp 1 |
| Smallest PQ signature footprint | 0.87 kB (Falcon-512) | Exp 3 |
| Per-item gas (Falcon-512) | 582 k gas | Exp 4 |
| Amortised batched gas (Falcon-512, N=256) | 324 gas | Exp 4 |
| Gas saving ratio (Falcon, N=256) | $\approx 1{,}795\times$ | Exp 4 |
| Watermark PSNR at $\Delta_0 = 16$ | $\geq 38$ dB | Exp 2 |
| Watermark bit-perfect recovery (noise-free) | 100 % | Exp 2 |
| AI-only in-distribution accuracy | 86.5 % | Exp 5 |
| AI + human in-distribution accuracy | 89.3 % | Exp 5 |

---

## Reproducing individual experiments

Each experiment is a standalone Python script. The general pattern is:

```bash
python -m experiments.exp1_signature_perf   # writes results/exp1_signature_perf.csv
python -m experiments.exp2_watermark_quality
python -m experiments.exp3_resource_consumption
python -m experiments.exp4_gas_cost
python -m experiments.exp5_detection_accuracy
```

`run_all.py` simply runs all five in sequence with consistent random seeds.

---

## Honest claims and limitations

This repository is engineered for transparent reproducibility, which includes being honest about what is and is not a real production implementation. The following caveats apply:

1. **The PQ signature wrapper is calibrated, not natively post-quantum-secure.** `src/crypto/pq_wrapper.py` reproduces FIPS-mandated key and signature sizes (Falcon-512: 666 B; Dilithium-5: 4 595 B; SLH-DSA-128s: 7 856 B) and reference-implementation latencies, but its internal authentication uses HMAC-SHA3-512 rather than the lattice or hash-tree hardness of the named schemes. Production deployments **must** enable the real backend by setting the environment variable `DPF_USE_OQS=1`, which routes signing / verification through liboqs.
2. **The Ethereum component is a gas-accurate simulator, not a mainnet client.** `src/blockchain/blockchain_sim.py` implements the post-Berlin / EIP-2929 / EIP-3529 gas schedule and is byte-exact against the Yellow Paper formula, but transactions are never broadcast.
3. **The synthetic dataset is parametric, not real face-swap video.** `data/generate_synthetic.py` produces 1/$f$-spectrum colour images with brightness shift, Gaussian-blended boundary, and a faint $4{\times}4$ checker residual — a stand-in for real GAN-pipeline artefacts, sufficient for testing the framework's relative algorithmic ordering but **not** a substitute for FaceForensics++ or DFDC benchmark scores.
4. **The cross-distribution direction is reversed on synthetic data.** Cross-distribution accuracy (92.3 %) is *higher* than in-distribution (86.5 %) because the cross-distribution generator applies the perturbation twice, strengthening the very cues the detector keys on. This is a known limitation of synthetic deepfake benchmarks; the cross-distribution row should be read as a sanity check that the framework returns sensible verdicts on a strictly different distribution, **not** as a real-world generalisation upper bound. See Section 4.6 of the paper for the full explanation.
5. **The human-loop boost is at the edge of statistical significance.** The +2.8 percentage-point boost from routing $[0.4, 0.6]$ items through the panel is a point estimate at $n = 400$ whose 95 % Wilson confidence interval overlaps the AI-only baseline. A deployment study with $n \geq 1\,000$ is required to bound the boost tightly.

---

## Data availability

All datasets generated and analysed in the paper are released with this repository.

* **Synthetic images** used in Experiments 1–5 are regenerated deterministically by `data/generate_synthetic.py` from documented random seeds. No external download is required.
* **Raw CSV outputs** of every experiment are committed under `results/`. These are the *source of every numeric value* in Tables 4–9 and Figures 6–11 of the paper.
* The CSVs are additionally **embedded inline** as readable tables in Section S2 of the supplementary file (`paper/dpf-supplementary.tex`), so readers can re-derive every result without running any code.

### Third-party datasets referenced (not used in our experiments)

Three public benchmark datasets are discussed in the literature review of the paper as comparative anchors; they are **not** used as input to our experiments and are not redistributed by us.

| Dataset | Persistent URL | Access |
|---|---|---|
| FaceForensics++ (Rössler et al., 2019) | https://github.com/ondyari/FaceForensics | Google form gated |
| DeepFake Detection Challenge (Dolhansky et al., 2020) | https://ai.meta.com/datasets/dfdc/ | Meta AI ToU |
| DFDC (Kaggle mirror) | https://www.kaggle.com/c/deepfake-detection-challenge | Kaggle account |
| WaveFake (Frank & Schönherr, 2021) | https://zenodo.org/records/5642694 | CC-BY-NC-SA 4.0 |

---

## Citation

If this repository or the accompanying paper helps your work, please cite as:

```bibtex
@article{yadav2026dpf,
  title   = {Implementation and Evaluation of a Multifaceted Deepfake Prevention Framework},
  author  = {Yadav, Nitu and Sheoran, Savita and Yadav, Deepak},
  journal = {(under review)},
  year    = {2026},
  note    = {Companion artefact: \url{https://github.com/USER/dpf}}
}
```

A `CITATION.cff` file is provided so GitHub renders a "Cite this repository" button automatically.

---

## License

All code, the Solidity contract, the synthetic data generator, the experiment drivers, the unit tests, and the LaTeX manuscript sources are released under the **MIT License** (see `LICENSE`).

The third-party benchmark datasets referenced in the paper (FaceForensics++, DFDC, WaveFake) remain under their respective licenses; this repository does **not** include them and does **not** redistribute them.

---

## Contributing

Pull requests are welcome. The intended extension paths, in approximate priority order, are:

1. **Real liboqs backend** — replace the HMAC fallback in `pq_wrapper.py` with `oqs.Signature("Falcon-512")` etc., gated by the `DPF_USE_OQS` environment variable.
2. **Real production detector** — drop in an Xception checkpoint exported via ONNX in place of the 14-feature gradient-boosted tree.
3. **Real Ethereum back-end** — replace the simulator in `blockchain_sim.py` with a `web3.py` client; the API is identical.
4. **Federated detection** — federate the detector across multiple platforms without sharing training data (the third gap from Alkhatib (2025) which the paper leaves as future work).
5. **Adversarial-removal robustness study** — quantify the watermark survival rate against deliberate (not incidental) JPEG / scaling / rotation / GAN-purification attacks.

---

## Contact

For questions or issues:

* Open an issue on GitHub: https://github.com/USER/dpf/issues
* Email the corresponding author: niturao.2810@gmail.com

The authors thank the editor and reviewers for the constructive feedback that led to this artefact.
