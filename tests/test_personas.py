"""Custom investor validation: good profiles pass, malformed ones get a readable message."""
import pytest

from src.personas import PersonaError, validate
from src.rules import evaluate

GOOD = {"id": "custom-ab12", "name": "Lea", "age": 33, "risk_tolerance": "moderate", "knowledge_level": "novice",
        "goals": [{"label": "Emergency", "horizon_years": 0}, {"label": "House in 4 years", "horizon_years": 4}],
        "holdings": [{"ticker": "CASH", "value_cad": 6000, "goal": "g1"}, {"ticker": "XBB.TO", "value_cad": 20000, "goal": "g2"},
                     {"ticker": "XEQT.TO", "value_cad": 10000, "goal": "g2"}],
        "constraints": {"min_liquid_cad": 5000, "max_single_position_pct": 10, "exclude_fossil_fuels": True}}


def test_valid_custom_investor_runs_through_rules():
    p = validate(GOOD)
    assert p["custom"] and p["constraints"]["excluded_sectors"] == ["Energy"] and p["preferences"]["esg_important"]
    ev = evaluate(p, p["holdings"], dict(action="buy", ticker="TSLA", amount_cad=15000, goal_id="g2", funding="new_money"))
    assert ev["ceiling"] == "INCONSISTENT"  # 4-year house money into Tesla


@pytest.mark.parametrize("patch,msg", [
    ({"id": "robert"}, "invalid id"), ({"age": 12}, "Age"), ({"risk_tolerance": "yolo"}, "risk profile"),
    ({"goals": []}, "goals"), ({"holdings": [{"ticker": "FAKE", "value_cad": 10, "goal": "g1"}]}, "pick an asset"),
    ({"holdings": [{"ticker": "SPY", "value_cad": 10, "goal": "g9"}]}, "which goal"),
    ({"constraints": {"max_crypto_pct": 300}}, "Max in crypto"),
])
def test_bad_profiles_get_readable_errors(patch, msg):
    with pytest.raises(PersonaError, match=msg):
        validate({**GOOD, **patch})
