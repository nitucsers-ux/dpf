"""End-to-end pipeline test: publish + verify in one round trip."""
from __future__ import annotations

import numpy as np
import pytest

from data.generate_synthetic import make_authentic
from src.pipeline import Pipeline


def test_publish_returns_a_media_id_and_gas_cost():
    p = Pipeline(algorithm="Falcon-512")
    image = make_authentic(0)
    res = p.publish(image, metadata={"title": "test", "creator": "alice"})
    assert len(res.media_id) == 32
    assert res.gas_cost > 0
    assert res.on_chain or res.rejected_reason is not None


def test_verify_runs_without_error_on_a_watermarked_image():
    """We don't assert verdict==authentic because the detector is untrained
    in this fast test; we only assert the pipeline runs end-to-end."""
    p = Pipeline(algorithm="Falcon-512")
    image = make_authentic(1)
    res = p.publish(image, metadata={"title": "test"})
    v = p.verify(res.watermarked, metadata={"title": "test"})
    assert v.verdict in {"authentic", "fake", "uncertain"}
    assert isinstance(v.detector_score, float)


def test_policy_engine_logs_publish_event():
    p = Pipeline(algorithm="Falcon-512")
    image = make_authentic(2)
    p.publish(image, metadata={"title": "x"})
    rule_ids = {inc.rule_id for inc in p.policy.incidents}
    assert "R4-publish-success" in rule_ids
