"""Tests for the gas-accurate Ethereum simulator and Merkle layout."""
from __future__ import annotations

import hashlib

import pytest

from src.blockchain.blockchain_sim import (
    BlockchainSim,
    amortised_batch_gas,
)


def test_register_media_costs_more_than_base():
    sim = BlockchainSim()
    receipt = sim.register_media(b"\x11" * 32, b"\x00" * 666, b"x" * 213)
    assert receipt.total > 21_000


def test_batched_path_storage_is_constant():
    """publishBatch writes one fresh slot regardless of N."""
    sim = BlockchainSim()
    leaves_64 = [hashlib.sha3_256(f"a{i}".encode()).digest() for i in range(64)]
    leaves_1k = [hashlib.sha3_256(f"a{i}".encode()).digest() for i in range(1024)]
    r1, _ = sim.publish_batch(leaves_64)
    sim2 = BlockchainSim()
    r2, _ = sim2.publish_batch(leaves_1k)
    # Storage cost is identical; only the root is written
    assert r1.storage_gas == r2.storage_gas


def test_merkle_root_deterministic():
    sim = BlockchainSim()
    leaves = [bytes([i]) * 32 for i in range(4)]
    r1, root1 = sim.publish_batch(leaves)
    sim2 = BlockchainSim()
    r2, root2 = sim2.publish_batch(leaves)
    assert root1 == root2
    assert len(root1) == 32


def test_amortised_gas_at_n_256_is_in_low_hundreds():
    g = amortised_batch_gas(n=256)
    assert g < 500, f"expected amortised gas < 500 at N=256, got {g}"
