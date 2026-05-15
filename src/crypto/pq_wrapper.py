"""Backward-compatibility alias for :mod:`src.crypto.dsa_wrapper`.

The dpf README and several earlier scripts reference ``src.crypto.pq_wrapper``
because the wrapper originally covered post-quantum schemes only. After it
was extended to also wrap classical RSA / ECDSA, the canonical name became
:mod:`src.crypto.dsa_wrapper`. Both module paths resolve to the same code.
"""
from .dsa_wrapper import ALGORITHMS, AlgorithmSpec, keygen, sign, verify

__all__ = ["ALGORITHMS", "AlgorithmSpec", "keygen", "sign", "verify"]
