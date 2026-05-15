"""Tests for the DWT--SVD-aware QIM watermark."""
from __future__ import annotations

import numpy as np
import pytest

from data.generate_synthetic import make_authentic
from src.watermarking.dwt_svd_hybrid import (
    embed,
    extract,
    pack_payload,
    psnr,
    unpack_payload,
)


def test_framing_roundtrip():
    sig = b"\x42" * 666
    meta = b"x" * 213
    blob = pack_payload(sig, meta)
    rec_sig, rec_meta = unpack_payload(blob)
    assert rec_sig == sig
    assert rec_meta == meta


def test_watermark_recovery_at_step_16():
    host = make_authentic(0)
    payload = pack_payload(b"\x00" * 666, b"y" * 213)
    wm = embed(host, payload, step=16, redundancy=3)
    recovered = extract(wm, n_bytes=len(payload), step=16, redundancy=3)
    assert recovered == payload, "watermark must round-trip bit-perfectly at step=16"


def test_psnr_at_step_16_is_reasonable():
    host = make_authentic(0)
    payload = pack_payload(b"\x00" * 666, b"y" * 213)
    wm = embed(host, payload, step=16, redundancy=3)
    p = psnr(host, wm)
    assert p > 30.0, f"PSNR was {p:.1f} dB; expected > 30 dB at default settings"


def test_oversized_payload_rejected():
    host = make_authentic(0)
    huge = b"\x00" * 10**6
    with pytest.raises(ValueError):
        embed(host, huge)
