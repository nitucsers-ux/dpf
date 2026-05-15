"""Calibrated digital-signature wrapper (classical + post-quantum)."""
from .dsa_wrapper import ALGORITHMS, AlgorithmSpec, keygen, sign, verify

__all__ = ["ALGORITHMS", "AlgorithmSpec", "keygen", "sign", "verify"]
