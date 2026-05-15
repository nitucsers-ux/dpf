"""
Policy and governance engine (Module 4 of the framework).

Evaluates user-defined rules against pipeline events and emits typed
incidents (Info / Warning / Critical) that are routed to operations,
human reviewers, takedown teams, and law-enforcement contacts.

The engine is JSONL-audited: every incident is appended to an audit log
that production deployments can persist to an immutable store. The
audit format is intentionally simple so it can be ingested by any SIEM.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class Severity(str, Enum):
    INFO     = "info"
    WARNING  = "warning"
    CRITICAL = "critical"


@dataclass
class Incident:
    rule_id: str
    severity: Severity
    timestamp: float
    payload: Dict[str, Any] = field(default_factory=dict)
    route_to: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d


@dataclass
class Rule:
    rule_id: str
    severity: Severity
    predicate: Callable[[Dict[str, Any]], bool]
    route_to: List[str] = field(default_factory=list)
    description: str = ""


class PolicyEngine:
    """In-memory engine; production swaps the audit_path for durable storage."""

    def __init__(self, audit_path: Optional[Path] = None) -> None:
        self.rules: List[Rule] = []
        self.incidents: List[Incident] = []
        self.audit_path = Path(audit_path) if audit_path else None
        if self.audit_path:
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)

    def add_rule(self, rule: Rule) -> None:
        self.rules.append(rule)

    def evaluate(self, event: Dict[str, Any]) -> List[Incident]:
        """Evaluate one event against every rule. Returns matched incidents."""
        matched: List[Incident] = []
        for r in self.rules:
            try:
                if r.predicate(event):
                    inc = Incident(
                        rule_id=r.rule_id,
                        severity=r.severity,
                        timestamp=time.time(),
                        payload=dict(event),
                        route_to=list(r.route_to),
                    )
                    self.incidents.append(inc)
                    matched.append(inc)
                    self._audit(inc)
            except Exception:  # noqa: BLE001 -- rules must be sandboxed
                continue
        return matched

    def _audit(self, incident: Incident) -> None:
        if not self.audit_path:
            return
        with open(self.audit_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(incident.to_dict()) + "\n")


# ---------------------------------------------------------------------------
# Built-in rule set (matches the paper's Section 3.6)
# ---------------------------------------------------------------------------
def build_default_engine(audit_path: Optional[Path] = None) -> PolicyEngine:
    engine = PolicyEngine(audit_path=audit_path)

    engine.add_rule(Rule(
        rule_id="R1-signature-invalid",
        severity=Severity.CRITICAL,
        predicate=lambda e: e.get("signature_valid") is False,
        route_to=["ops", "law-enforcement"],
        description="The signature on this submission failed verification.",
    ))
    engine.add_rule(Rule(
        rule_id="R2-detector-flagged-fake",
        severity=Severity.CRITICAL,
        predicate=lambda e: e.get("detector_score", 0.0) > 0.6,
        route_to=["ops", "takedown"],
        description="The detector flagged this submission as a deepfake.",
    ))
    engine.add_rule(Rule(
        rule_id="R3-detector-uncertain",
        severity=Severity.WARNING,
        predicate=lambda e: 0.4 <= e.get("detector_score", 0.0) <= 0.6,
        route_to=["human-review"],
        description="Detector score is in the uncertain band [0.4, 0.6].",
    ))
    engine.add_rule(Rule(
        rule_id="R4-publish-success",
        severity=Severity.INFO,
        predicate=lambda e: e.get("event") == "publish-ok",
        route_to=["ops"],
        description="A media item was successfully registered.",
    ))
    return engine
