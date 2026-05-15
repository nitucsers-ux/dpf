"""
Synthetic image generator for the dpf reproducibility artefact.

Produces three populations of 512x512x3 uint8 RGB images:
  * authentic    -- 1/f-spectrum colour noise
  * manipulated  -- authentic + parametric face-swap-style perturbation
                   (brightness shift, Gaussian-blended boundary, 4x4 checker
                    residual that imitates the GAN upsampling fingerprint of
                    Carlini & Farid, CVPRW 2020)
  * cross_dist   -- the same perturbation applied TWICE; used in Exp 5 to
                   measure the framework's behaviour on a strictly different
                   distribution.

All seeds are documented; the output is bit-exact reproducible on any
platform with NumPy >= 1.24.

CLI:
    python -m data.generate_synthetic --out data/synthetic
"""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# Seeds (documented in Table S5 of the supplementary)
# ---------------------------------------------------------------------------
SEED_AUTH_TRAIN          = 0       # 0..999
SEED_AUTH_INDIST_TEST    = 1_000   # 1000..1199  (200 authentic, in-dist test)
SEED_AUTH_CROSSDIST_TEST = 2_000   # 2000..2199  (200 authentic, cross-dist)
SEED_WM_HOST             = 0       # 0..19       (20 watermark host images)
SEED_MASTER              = 42      # ensembles, jitter, panel draws

IMG_H, IMG_W = 512, 512


# ---------------------------------------------------------------------------
# Core generators
# ---------------------------------------------------------------------------
def _onef_image(seed: int) -> np.ndarray:
    """1/f-spectrum colour noise -- second-order statistics close to natural."""
    rng = np.random.default_rng(seed)
    # Build amplitude spectrum  A(u,v) = 1 / sqrt(u^2 + v^2)
    fy = np.fft.fftfreq(IMG_H)[:, None]
    fx = np.fft.fftfreq(IMG_W)[None, :]
    radius = np.sqrt(fx ** 2 + fy ** 2)
    radius[0, 0] = 1.0  # avoid divide-by-zero at DC
    amp = 1.0 / radius

    channels = []
    for _ in range(3):
        phase = rng.uniform(0.0, 2 * np.pi, (IMG_H, IMG_W))
        spectrum = amp * np.exp(1j * phase)
        img = np.fft.ifft2(spectrum).real
        # Normalise to [0, 255]
        img = (img - img.min()) / (img.max() - img.min())
        channels.append((img * 255).astype(np.uint8))
    return np.stack(channels, axis=-1)


def _apply_perturbation(img: np.ndarray, seed: int) -> np.ndarray:
    """Single parametric face-swap-style artefact:
       (i) brightness shift in a centred patch,
       (ii) Gaussian-blended boundary (5 px),
       (iii) faint 4x4 checker residual that imitates GAN upsampling.
    """
    rng = np.random.default_rng(seed)
    h, w = img.shape[:2]
    out = img.astype(np.float32).copy()

    # Centred patch (~37 % of the smaller dim)
    patch = int(0.37 * min(h, w))
    cy, cx = h // 2, w // 2
    y0, y1 = cy - patch // 2, cy + patch // 2
    x0, x1 = cx - patch // 2, cx + patch // 2

    # (i) brightness shift
    delta = rng.integers(8, 24)
    out[y0:y1, x0:x1] += float(delta)

    # (ii) Gaussian-blended boundary
    radius = 5
    yy, xx = np.ogrid[-radius:radius + 1, -radius:radius + 1]
    g = np.exp(-(xx ** 2 + yy ** 2) / (2 * (radius / 2) ** 2))
    g = g / g.sum()
    # crude boundary smoothing: shrink + grow the patch using a soft mask
    mask = np.zeros((h, w), dtype=np.float32)
    mask[y0:y1, x0:x1] = 1.0
    # apply Gaussian via row+col separable convolution (simple, deterministic)
    from scipy.ndimage import gaussian_filter
    soft = gaussian_filter(mask, sigma=2.0)
    out = out * (1 - soft[..., None]) + (out + delta) * soft[..., None]

    # (iii) 4x4 checker residual
    checker = np.tile(np.array([[1, -1], [-1, 1]], dtype=np.float32), (2, 2))
    checker = np.repeat(np.repeat(checker, 1, axis=0), 1, axis=1)  # 4x4
    tile = np.tile(checker, (h // 4, w // 4))
    out[..., 0] += 0.8 * tile  # very faint
    out[..., 1] += 0.8 * tile
    out[..., 2] += 0.8 * tile

    return np.clip(out, 0, 255).astype(np.uint8)


def make_authentic(seed: int) -> np.ndarray:
    return _onef_image(seed)


def make_manipulated(seed: int) -> np.ndarray:
    base = _onef_image(seed)
    return _apply_perturbation(base, seed)


def make_cross_dist(seed: int) -> np.ndarray:
    """Cross-distribution: apply the perturbation twice."""
    base = _onef_image(seed)
    once = _apply_perturbation(base, seed)
    twice = _apply_perturbation(once, seed + 10_000)
    return twice


# ---------------------------------------------------------------------------
# Bulk dataset generation
# ---------------------------------------------------------------------------
@dataclass
class DatasetSpec:
    n_train_per_class: int = 500    # 500 authentic + 500 manipulated  = 1000
    n_test_per_class:  int = 200    # 200 authentic + 200 manipulated  = 400
    n_crossdist_per_class: int = 200  # 200 + 200 = 400
    n_wm_host: int = 20


def regenerate_all(out_dir: Path, spec: DatasetSpec | None = None) -> dict:
    """Regenerate every synthetic image used in Experiments 1-5.

    Returns a manifest dict of {category: file_count} so callers can verify.
    """
    spec = spec or DatasetSpec()
    out_dir = Path(out_dir)
    manifest: dict[str, int] = {}

    def _dump(category: str, factory, seed_base: int, n: int) -> None:
        d = out_dir / category
        d.mkdir(parents=True, exist_ok=True)
        for i in range(n):
            arr = factory(seed_base + i)
            Image.fromarray(arr).save(d / f"{i:04d}.png", optimize=False)
        manifest[category] = n

    # Watermark host images (20)
    _dump("wm_host", make_authentic, SEED_WM_HOST, spec.n_wm_host)

    # Training split (1 000)
    _dump("train/authentic",
          make_authentic, SEED_AUTH_TRAIN, spec.n_train_per_class)
    _dump("train/manipulated",
          make_manipulated, SEED_AUTH_TRAIN + 10_000, spec.n_train_per_class)

    # In-distribution test split (400)
    _dump("test_indist/authentic",
          make_authentic, SEED_AUTH_INDIST_TEST, spec.n_test_per_class)
    _dump("test_indist/manipulated",
          make_manipulated, SEED_AUTH_INDIST_TEST + 10_000, spec.n_test_per_class)

    # Cross-distribution test split (400)
    _dump("test_crossdist/authentic",
          make_authentic, SEED_AUTH_CROSSDIST_TEST,
          spec.n_crossdist_per_class)
    _dump("test_crossdist/manipulated",
          make_cross_dist, SEED_AUTH_CROSSDIST_TEST + 10_000,
          spec.n_crossdist_per_class)

    total = sum(manifest.values())
    print(f"Generated {total} images across {len(manifest)} splits.")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("data/synthetic"),
                    help="Output root directory.")
    args = ap.parse_args()
    regenerate_all(args.out)


if __name__ == "__main__":
    main()
