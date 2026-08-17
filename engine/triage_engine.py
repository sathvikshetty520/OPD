"""
Deterministic protocol-based triage engine.

Loads protocol/rules.yaml and scores a structured intake into
(tier, department, matched_rules, escalate). Every decision traces
back to specific rule IDs for auditability. This module does NOT
call any LLM or make probabilistic judgments -- symptom-to-structured
extraction (if done via LLM) must happen upstream, before this point.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

RULES_PATH = Path(__file__).parent.parent / "protocol" / "rules.yaml"


@dataclass
class Intake:
    patient_token: str
    complaint_id: str              # must match a key under `complaints` in rules.yaml
    red_flag_ids: list[str] = field(default_factory=list)


@dataclass
class TriageResult:
    case_id: str
    patient_token: str
    tier: str
    tier_label: str
    department: str
    matched_rules: list[str]
    escalate: bool
    escalate_reason: str | None
    protocol_version: str
    timestamp: str

    def to_audit_record(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "patient_token": self.patient_token,
            "tier": self.tier,
            "department": self.department,
            "matched_rules": self.matched_rules,
            "escalate": self.escalate,
            "escalate_reason": self.escalate_reason,
            "protocol_version": self.protocol_version,
            "timestamp": self.timestamp,
        }


class UnknownComplaintError(Exception):
    """Raised when complaint_id doesn't match any rule -- caller should route to human review."""


class TriageEngine:
    def __init__(self, rules_path: Path = RULES_PATH):
        with open(rules_path) as f:
            self.rules = yaml.safe_load(f)
        self.version = self.rules["version"]

    def score(self, intake: Intake) -> TriageResult:
        matched: list[str] = []
        red_flags = self.rules["red_flags"]
        flag_by_id = {f["id"]: f for f in red_flags}

        hit_flags = [fid for fid in intake.red_flag_ids if fid in flag_by_id]

        complaints = self.rules["complaints"]
        if intake.complaint_id not in complaints:
            # Unrecognized input: never guess. Force human review.
            return TriageResult(
                case_id=str(uuid.uuid4()),
                patient_token=intake.patient_token,
                tier="unrecognized",
                tier_label="Unrecognized -- human review required",
                department="Front-desk triage (manual)",
                matched_rules=["no complaint category matched -> mandatory human review"],
                escalate=True,
                escalate_reason="unrecognized_complaint",
                protocol_version=self.version,
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )

        complaint = complaints[intake.complaint_id]
        tier = complaint["base_tier"]
        department = complaint["department"]
        matched.append(
            f"complaint_rule:{intake.complaint_id} -> base_tier={tier}, dept={department}"
        )

        escalate = False
        escalate_reason = None

        if hit_flags:
            tier = "emergency"
            department = "Emergency (staff review required)"
            for fid in hit_flags:
                matched.append(f"red_flag:{fid} ({flag_by_id[fid]['label']}) -> tier=emergency")
            escalate = True
            escalate_reason = "red_flag"
        elif self.rules["escalation"]["emergency_requires_human_review"] and tier == "emergency":
            escalate = True
            escalate_reason = "emergency_tier"

        tier_label = self.rules["tiers"][tier]["label"]

        return TriageResult(
            case_id=str(uuid.uuid4()),
            patient_token=intake.patient_token,
            tier=tier,
            tier_label=tier_label,
            department=department,
            matched_rules=matched,
            escalate=escalate,
            escalate_reason=escalate_reason,
            protocol_version=self.version,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )


if __name__ == "__main__":
    engine = TriageEngine()
    demo = Intake(patient_token="T-104", complaint_id="chest_pain", red_flag_ids=["pain_9_10"])
    result = engine.score(demo)
    import json
    print(json.dumps(result.to_audit_record(), indent=2))
