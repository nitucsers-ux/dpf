# Contributing

Pull requests are welcome. The intended extension paths, in approximate priority order, are:

## 1. Real liboqs backend

Replace the HMAC fallback inside `src/crypto/dsa_wrapper.py` with `oqs.Signature("Falcon-512")` etc. The structure is already in place: setting the `DPF_USE_OQS=1` environment variable routes through liboqs.

```bash
pip install liboqs-python
export DPF_USE_OQS=1
pytest tests/test_crypto.py -v
```

## 2. Real production detector

Drop in an Xception checkpoint exported via ONNX in place of the 14-feature gradient-boosted tree. The `FakeDetector.predict_proba` API is the only surface area that needs to be preserved.

```python
class FakeDetector:
    def predict_proba(self, X):
        # Replace this with ort.InferenceSession run
        ...
```

## 3. Real Ethereum back-end

Replace `BlockchainSim` with a `web3.py` client. The class API (`register_media`, `set_status`, `publish_batch`, `verify_inclusion`) is intentionally aligned with the Solidity contract `src/blockchain/MediaRegistry.sol`, so the swap is mechanical.

## 4. Federated detection

Federate the detector across multiple platforms without sharing training data — the third gap from Alkhatib (2025) that this paper leaves as future work. FedAvg (McMahan et al., AISTATS 2017) is a natural starting point.

## 5. Adversarial-removal robustness study

Quantify the watermark survival rate against deliberate attacks (not incidental JPEG compression):

* Adversarial perturbations targeting the QIM lattice
* GAN-based purification (e.g. via DDPM-style purification)
* Geometric attacks (rotation, scaling, cropping)

The current watermark survives JPEG quality 80 informally; a thorough adversarial study is the natural extension.

## Code style

* Follow PEP 8.
* Type-hint public APIs.
* Add a docstring with at least a one-line summary.
* Add a test in `tests/` for every new behaviour.

## Running tests

```bash
pip install -e .[test]
pytest tests/ -v
```

CI runs the full suite on Python 3.10, 3.11, and 3.12.

## Filing issues

Please include:

1. Python version (`python --version`)
2. OS and architecture
3. Output of `pip freeze`
4. The minimal reproducer
