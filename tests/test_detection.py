"""Tests for the detector and the human-in-the-loop panel."""
from __future__ import annotations

import numpy as np
import pytest

from data.generate_synthetic import make_authentic, make_manipulated
from src.detection.detector import FakeDetector, extract_features
from src.human_loop.panel import HumanPanel


def test_feature_vector_has_14_dims():
    img = make_authentic(0)
    feats = extract_features(img)
    assert feats.shape == (14,)
    assert np.isfinite(feats).all()


def test_detector_learns_to_separate_classes():
    """With 50 + 50 simple samples it should beat 70 % on a held-out 20."""
    auth_train = [make_authentic(i) for i in range(50)]
    manip_train = [make_manipulated(i + 1000) for i in range(50)]
    X_train = np.stack([extract_features(im) for im in auth_train + manip_train])
    y_train = np.r_[np.zeros(50), np.ones(50)].astype(int)

    auth_test  = [make_authentic(i + 500)  for i in range(10)]
    manip_test = [make_manipulated(i + 2000) for i in range(10)]
    X_test = np.stack([extract_features(im) for im in auth_test + manip_test])
    y_test = np.r_[np.zeros(10), np.ones(10)].astype(int)

    det = FakeDetector(n_estimators=30, max_depth=3, random_state=42)
    det.fit(X_train, y_train)
    acc = (det.predict(X_test) == y_test).mean()
    assert acc > 0.70, f"detector hit {acc:.1%}; expected > 70 %"


def test_panel_accuracy_means_are_clipped():
    panel = HumanPanel(n_reviewers=10, seed=0)
    accs = panel.accuracies
    assert len(accs) == 10
    assert (accs >= 0.60).all() and (accs <= 0.99).all()


def test_panel_rates_in_1_to_10_range():
    panel = HumanPanel(seed=7)
    ratings = panel.rate_one(true_label=0, item_seed=42)
    assert (ratings >= 1).all() and (ratings <= 10).all()


def test_panel_verdict_uses_75_percent_threshold():
    panel = HumanPanel(seed=1)
    # All-9 ratings → mean 9 → > 7.5 → authentic
    assert panel.verdict(np.full(10, 9.0)) == "authentic"
    # All-3 ratings → mean 3 → < 7.5 → fake
    assert panel.verdict(np.full(10, 3.0)) == "fake"
