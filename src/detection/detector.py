"""
Feature-engineered deepfake detector.

A lightweight stand-in for the Xception / FaceForensics++ models that the
reference framework uses. Extracts 14 handcrafted features per image, trains
a gradient-boosted decision tree, and exposes a single `predict_proba` API.

This is intentionally simple so the detector path runs in milliseconds on a
single CPU core. A real production deployment should replace the feature
vector with an Xception checkpoint exported via ONNX (see
docs/CONTRIBUTING.md).

The 14 features capture artefact signatures that GAN / face-swap pipelines
tend to leave behind:

  0  Laplacian energy        (defocus / sharpness)
  1  FFT spectral slope      (1/f deviation)
  2  JPEG 8x8 grid variance  (compression-block residual)
  3  GAN 4x4 grid signature  (upsampling fingerprint)
  4  R-G colour residual     (chroma desync)
  5  R-B colour residual     (chroma desync)
  6  G-B colour residual     (chroma desync)
  7  Edge-jaggedness         (boundary smoothness)
  8  Local-variance std      (texture heterogeneity)
  9  High-frequency energy   (sharpness after downsample)
 10  Saturation skew         (colour-distribution shape)
 11  Hue entropy             (palette diversity)
 12  Patch mean delta        (centre vs surround)
 13  Local kurtosis          (noise non-Gaussianity)
"""
from __future__ import annotations

from typing import Tuple

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------
def extract_features(img: np.ndarray) -> np.ndarray:
    """14-dim feature vector for one H x W x 3 uint8 image."""
    img = img.astype(np.float32)
    h, w = img.shape[:2]
    gray = img.mean(axis=-1)

    # 0  Laplacian energy
    lap = (np.abs(np.diff(gray, axis=0, prepend=gray[:1])) +
           np.abs(np.diff(gray, axis=1, prepend=gray[:, :1]))).mean()

    # 1  FFT spectral slope (log power vs log radius, slope coefficient)
    f = np.fft.fftshift(np.fft.fft2(gray))
    power = np.abs(f) ** 2 + 1e-9
    fy = np.arange(h) - h / 2
    fx = np.arange(w) - w / 2
    radius = np.sqrt(fy[:, None] ** 2 + fx[None, :] ** 2) + 1
    # crude binning into 16 radial bins
    bins = np.clip((radius / radius.max() * 16).astype(int), 0, 15)
    binned = np.array([power[bins == k].mean() for k in range(16)])
    slope = np.polyfit(np.log1p(np.arange(16)), np.log(binned + 1e-9), 1)[0]

    # 2  JPEG 8x8 grid variance
    g8 = gray[: h - h % 8, : w - w % 8].reshape(h // 8, 8, w // 8, 8)
    grid_var_8 = float(g8.std(axis=(1, 3)).mean())

    # 3  GAN 4x4 grid signature
    g4 = gray[: h - h % 4, : w - w % 4].reshape(h // 4, 4, w // 4, 4)
    grid_var_4 = float(g4.std(axis=(1, 3)).mean())

    # 4-6 Colour-channel residuals
    rg = float(np.abs(img[..., 0] - img[..., 1]).mean())
    rb = float(np.abs(img[..., 0] - img[..., 2]).mean())
    gb = float(np.abs(img[..., 1] - img[..., 2]).mean())

    # 7  Edge-jaggedness: total-variation along rows minus along columns
    tv_y = float(np.abs(np.diff(gray, axis=0)).mean())
    tv_x = float(np.abs(np.diff(gray, axis=1)).mean())
    jaggedness = abs(tv_y - tv_x)

    # 8  Local-variance std
    blk = gray[: h - h % 16, : w - w % 16].reshape(h // 16, 16, w // 16, 16)
    local_var_std = float(blk.var(axis=(1, 3)).std())

    # 9  High-frequency energy (top 30% radial bins of FFT)
    hf_mask = bins >= 11
    hf_energy = float(power[hf_mask].mean())

    # 10 Saturation skew (using max-min as proxy)
    sat = img.max(axis=-1) - img.min(axis=-1)
    sat_skew = float(np.mean((sat - sat.mean()) ** 3) /
                     (sat.std() ** 3 + 1e-9))

    # 11 Hue entropy (32-bin histogram of arctan2(g-b, r-g))
    hue = np.arctan2(img[..., 1] - img[..., 2],
                     img[..., 0] - img[..., 1] + 1e-9)
    hist, _ = np.histogram(hue, bins=32, density=True)
    hist = hist / (hist.sum() + 1e-9)
    hue_entropy = float(-(hist * np.log(hist + 1e-9)).sum())

    # 12 Patch mean delta (centre 37 % vs surround)
    patch = int(0.37 * min(h, w))
    cy, cx = h // 2, w // 2
    centre = gray[cy - patch // 2:cy + patch // 2,
                  cx - patch // 2:cx + patch // 2].mean()
    surround = (gray.sum() - gray[cy - patch // 2:cy + patch // 2,
                                  cx - patch // 2:cx + patch // 2].sum()) / \
               (gray.size - patch * patch)
    patch_delta = float(abs(centre - surround))

    # 13 Local kurtosis
    diffs = gray - gray.mean()
    kurt = float((diffs ** 4).mean() / ((diffs ** 2).mean() ** 2 + 1e-9))

    return np.array([
        lap, slope, grid_var_8, grid_var_4,
        rg, rb, gb,
        jaggedness, local_var_std, hf_energy,
        sat_skew, hue_entropy, patch_delta, kurt,
    ], dtype=np.float32)


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------
class FakeDetector:
    """Wrapper around scikit-learn GradientBoostingClassifier."""

    def __init__(self, n_estimators: int = 80, max_depth: int = 3,
                 random_state: int = 42) -> None:
        self.clf = GradientBoostingClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=random_state,
        )

    def fit(self, X: np.ndarray, y: np.ndarray) -> "FakeDetector":
        self.clf.fit(X, y)
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Probability that each row is *manipulated* (class 1)."""
        return self.clf.predict_proba(X)[:, 1]

    def predict(self, X: np.ndarray, threshold: float = 0.5) -> np.ndarray:
        return (self.predict_proba(X) > threshold).astype(np.int32)


def featurise_dataset(images: list[np.ndarray]) -> np.ndarray:
    """Apply `extract_features` over a list of images, returning a (N, 14) array."""
    return np.stack([extract_features(im) for im in images])
