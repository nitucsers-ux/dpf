# Architecture

This document maps the four modules of Alkhatib's multifaceted prevention framework to the source files in this repository.

```
┌──────────────────────────────────────────────────────────────┐
│                      src/pipeline.py                          │
│  orchestrates Scenario A (publish) and Scenario B (verify)    │
└─────┬──────────────┬──────────────┬──────────────┬───────────┘
      │              │              │              │
      ▼              ▼              ▼              ▼
┌───────────┐ ┌─────────────┐ ┌───────────┐ ┌──────────────┐
│ M1: Trust │ │M2: Detection│ │M3: Human  │ │M4: Policy &  │
│ Assurance │ │& Monitoring │ │in the Loop│ │Governance    │
└───────────┘ └─────────────┘ └───────────┘ └──────────────┘
      │              │              │              │
      │              │              │              │
src/crypto/    src/detection/  src/human_loop/  src/policy/
src/watermarking/                                    
src/blockchain/                                      
```

## Module 1 — Trusted Content Assurance

Three files cooperate:

| File | Role |
|---|---|
| `src/crypto/dsa_wrapper.py` | Calibrated wrapper around RSA, ECDSA, Dilithium-5, Falcon-512, SLH-DSA-128s. FIPS-mandated sizes. `DPF_USE_OQS=1` switches to liboqs. |
| `src/watermarking/dwt_svd_hybrid.py` | Hybrid DWT + SVD + QIM embedder/extractor; embeds (sig + metadata + DPF1 header) into the green channel's haar wavelet detail sub-bands. |
| `src/blockchain/blockchain_sim.py` | Gas-accurate Ethereum simulator. Implements both the per-item registration path (Alkhatib's layout) and our Merkle-batched layout. |
| `src/blockchain/MediaRegistry.sol` | The Solidity contract that the simulator mirrors byte-for-byte. |

## Module 2 — Detection and Monitoring

One file, `src/detection/detector.py`. Extracts 14 hand-crafted features per image (Laplacian energy, FFT spectral slope, JPEG-grid variance, GAN-grid signature, colour residuals, etc.) and trains a gradient-boosted decision tree.

A real production deployment should replace this with an Xception checkpoint exported via ONNX; the `predict_proba` API is intentionally identical so the swap is one line.

## Module 3 — Awareness, Training, and Human-in-the-Loop

`src/human_loop/panel.py`. A simulated 10-expert Likert panel with per-reviewer accuracy drawn from `N(0.90, 0.05)` clipped to `[0.60, 0.99]`. Verdict aggregation uses the 75 %-threshold rule of Alkhatib (2025).

## Module 4 — Policy, Governance, and Regulation

`src/policy/engine.py`. A rule engine that evaluates pipeline events against user-defined predicates and emits typed incidents (`Info` / `Warning` / `Critical`) routed to operations, human reviewers, takedown teams, and law enforcement.

Includes a JSONL audit trail (one line per incident) compatible with any SIEM.

## Data flow (Scenario A — publish)

```
image + metadata
     │
     ▼
sha3-256(image || metadata)  ── media_id ──────────────────┐
     │                                                      │
     ▼                                                      │
sign(sk, media_id) ── signature ──┐                        │
     │                             │                        │
     │                             ▼                        │
     │                pack_payload(sig, meta) ── payload    │
     │                             │                        │
     ▼                             ▼                        ▼
extract_features() ──── score    embed() ── watermarked    register_media()
     │                  (0.6+)                                      │
     │                rejected                                       ▼
     │                  by M4                                  GasReceipt
     ▼                                                              │
policy.evaluate() ◀─────────────────────────────────────────────────┘
```

## Data flow (Scenario B — verify)

```
watermarked image
     │
     ▼
extract() ── payload ── unpack_payload() ── (sig, meta)
     │                                            │
     ▼                                            ▼
extract_features() ── score              verify(pk, media_id, sig)
     │                                            │
     ▼                                            ▼
score in [0.4, 0.6]? ── YES ── route to panel ──> verdict
       │                                            │
       NO                                           ▼
       ▼                                       policy.evaluate()
   verdict = authentic / fake
```

## Why "calibrated" PQ wrapper

A production deployment of the framework MUST use real liboqs for the PQ schemes; the calibrated wrapper inside this repository:

1. Reproduces FIPS-mandated key and signature sizes exactly, so payload, watermark, and gas-cost experiments are bit-exact.
2. Reproduces NIST round-3 reference-implementation latencies through a calibration table, so the latency experiment also matches the source paper to within 6 %.
3. Does NOT inherit the lattice or hash-tree hardness of the named schemes. Internally it uses HMAC-SHA3-512 for authentication.

Setting the environment variable `DPF_USE_OQS=1` routes signing and verification through liboqs and recovers the genuine PQ hardness assumptions. Every other component is unchanged.

## Why "gas-accurate simulator"

For the gas-cost experiments to be reproducible offline, we needed a deterministic implementation of the Yellow-Paper formula that does not require an Ethereum node. `src/blockchain/blockchain_sim.py` implements:

| Constant | Value | Source |
|---|---|---|
| `G_TRANSACTION` | 21 000 | base transaction cost |
| `G_CALLDATA_ZERO` | 4 | per-byte zero calldata (EIP-2028) |
| `G_CALLDATA_NONZERO` | 16 | per-byte non-zero calldata (EIP-2028) |
| `G_SSTORE_NEW` | 20 000 | fresh 32-byte storage word (post-Berlin) |
| `G_LOG_BASE` | 375 | per LOG opcode |
| `G_LOG_TOPIC` | 375 | per indexed topic |
| `G_LOG_BYTE` | 8 | per byte of non-topic LOG data |

Replacing the simulator with a real mainnet client (`web3.py`) requires no other code change.
