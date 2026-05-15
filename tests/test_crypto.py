"""Tests for the calibrated DSA wrapper."""
from __future__ import annotations

import pytest

from src.crypto.dsa_wrapper import ALGORITHMS, keygen, sign, verify


@pytest.mark.parametrize("alg", list(ALGORITHMS))
def test_signature_has_fips_mandated_size(alg):
    spec = ALGORITHMS[alg]
    _, sk = keygen(alg)
    sig = sign(sk, b"\x00" * 64, alg)
    if spec.family == "classical":
        # Classical schemes have variable-size signatures (DER-encoded);
        # we assert "at most" rather than "exactly"
        assert len(sig) <= spec.sig_size + 32
    else:
        assert len(sig) == spec.sig_size, \
            f"{alg} produced {len(sig)}-byte sig, expected {spec.sig_size}"


def test_classical_roundtrip():
    """RSA and ECDSA via the cryptography library: sign/verify works."""
    for alg in ["RSA", "ECDSA"]:
        pk, sk = keygen(alg)
        msg = b"hello dpf"
        sig = sign(sk, msg, alg)
        assert verify(pk, msg, sig, alg)
        assert not verify(pk, msg + b"x", sig, alg)


def test_pq_sizes_match_fips():
    """The PQ wrapper produces signatures of exactly the FIPS-mandated sizes."""
    cases = {
        "Dilithium-5":  4595,
        "Falcon-512":    666,
        "SLH-DSA-128s": 7856,
    }
    for alg, expected in cases.items():
        _, sk = keygen(alg)
        sig = sign(sk, b"\x00" * 64, alg)
        assert len(sig) == expected
