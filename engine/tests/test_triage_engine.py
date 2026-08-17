import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from triage_engine import TriageEngine, Intake


@pytest.fixture
def engine():
    return TriageEngine()


def test_known_complaint_gets_base_tier(engine):
    r = engine.score(Intake(patient_token="T-1", complaint_id="minor_injury"))
    assert r.tier == "nonurgent"
    assert r.department == "Orthopedics"
    assert not r.escalate


def test_urgent_complaint_without_red_flags_does_not_escalate(engine):
    r = engine.score(Intake(patient_token="T-2", complaint_id="chest_pain"))
    assert r.tier == "urgent"
    assert not r.escalate


def test_any_red_flag_forces_emergency_and_escalation(engine):
    r = engine.score(Intake(patient_token="T-3", complaint_id="minor_injury", red_flag_ids=["active_bleeding"]))
    assert r.tier == "emergency"
    assert r.escalate is True
    assert r.escalate_reason == "red_flag"


def test_unrecognized_complaint_never_guesses(engine):
    r = engine.score(Intake(patient_token="T-4", complaint_id="not_a_real_category"))
    assert r.escalate is True
    assert r.escalate_reason == "unrecognized_complaint"


def test_every_matched_rule_is_traceable(engine):
    r = engine.score(Intake(patient_token="T-5", complaint_id="fever", red_flag_ids=["infant_fever"]))
    assert any("complaint_rule:fever" in m for m in r.matched_rules)
    assert any("red_flag:infant_fever" in m for m in r.matched_rules)


@pytest.mark.parametrize("flag_id", [
    "altered_consciousness", "airway_compromise", "breathing_difficulty_rest",
    "active_bleeding", "chest_pain_cardiac", "stroke_signs", "severe_trauma",
    "pain_9_10", "pregnancy_bleeding", "infant_fever", "self_harm_risk",
])
def test_all_red_flags_individually_force_emergency(engine, flag_id):
    r = engine.score(Intake(patient_token="T-flag", complaint_id="fever", red_flag_ids=[flag_id]))
    assert r.tier == "emergency", f"red flag {flag_id} did not force emergency tier"
