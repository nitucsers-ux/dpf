"""
Simulated 10-expert Likert panel for the framework's M3 module.

Reviewers issue 1-10 Likert ratings (10 = strongly authentic, 1 = strongly
fake). Per-reviewer accuracy is drawn from a clipped normal distribution
N(0.90, 0.05) at panel-construction time. The aggregation rule is the
75 %-threshold rule of Alkhatib (2025): an item is classified Authentic iff
the mean Likert rating across reviewers exceeds 7.5 (i.e., 75 % of the 1-10
scale).

This is a simulator, not a UI: it is meant to model the inter-rater
agreement structure in a controlled experiment, not to recruit humans. A
real deployment would replace the simulator with a web-based review queue
backed by an expert-reputation system.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass
class HumanPanel:
    """A panel of `n_reviewers` simulated experts."""
    n_reviewers: int = 10
    seed: int = 42

    def __post_init__(self) -> None:
        rng = np.random.default_rng(self.seed)
        # per-reviewer accuracy, clipped to [0.6, 0.99]
        accs = rng.normal(0.90, 0.05, self.n_reviewers)
        self._accuracies = np.clip(accs, 0.60, 0.99)

    @property
    def accuracies(self) -> np.ndarray:
        return self._accuracies.copy()

    def rate_one(self, true_label: int, item_seed: int) -> np.ndarray:
        """Generate one panel's worth of 1-10 Likert ratings for one item.

        true_label: 0 = authentic, 1 = manipulated
        item_seed: seed for this item's noise draw (different per item)
        """
        rng = np.random.default_rng(item_seed)
        # If a reviewer is "accurate", they vote near the truth; else near
        # the opposite end of the scale. Truth label 0 -> 10, label 1 -> 1.
        truth_score = 10 if true_label == 0 else 1
        opposite_score = 1 if true_label == 0 else 10
        ratings = []
        for acc in self._accuracies:
            correct = rng.random() < acc
            base = truth_score if correct else opposite_score
            # Add a small Gaussian jitter so ratings span a realistic range
            jitter = rng.normal(0.0, 0.5)
            ratings.append(float(np.clip(base + jitter, 1, 10)))
        return np.array(ratings)

    def verdict(self, ratings: np.ndarray) -> str:
        """Return 'authentic' iff the mean rating > 7.5 (75 % of 1-10)."""
        return "authentic" if ratings.mean() > 7.5 else "fake"

    def rate_and_decide(self, true_label: int, item_seed: int) -> str:
        return self.verdict(self.rate_one(true_label, item_seed))


def panel_accuracy_on_uncertain(true_labels: Sequence[int],
                                routed_idx: Sequence[int],
                                panel: HumanPanel,
                                base_seed: int = 1000) -> float:
    """Accuracy of the panel on the items that were routed for review."""
    if not routed_idx:
        return float("nan")
    correct = 0
    for i in routed_idx:
        v = panel.rate_and_decide(true_labels[i], base_seed + i)
        if (v == "authentic" and true_labels[i] == 0) or \
           (v == "fake"      and true_labels[i] == 1):
            correct += 1
    return correct / len(routed_idx)
