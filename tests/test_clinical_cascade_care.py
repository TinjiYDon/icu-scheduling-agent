"""Unit tests for H7 RFCC gate + CARE/UHRM indices."""

from domain.ops.care_index import compute_care, unserved_high_risk_mass
from domain.optimizer.clinical_cascade import cascade_meta, cascade_order, scarcity_triggered


def test_scarcity_gate_orders():
    assert scarcity_triggered(25, 20) is True
    assert scarcity_triggered(20, 20) is True  # 1:1 still triage
    assert scarcity_triggered(10, 20) is False
    scarce = cascade_order(25, 20)
    abound = cascade_order(10, 20)
    assert scarce[0] == "high_risk"
    assert abound[0] == "occupancy"
    meta = cascade_meta(25, 20)
    assert meta["gate"] == "scarcity"
    assert meta["mechanism"] == "RFCC"


def test_care_and_uhrm():
    cands = [
        {"stay_id": 1, "sofa_total": 12, "priority_weight": 4.0},
        {"stay_id": 2, "sofa_total": 11, "priority_weight": 3.0},
        {"stay_id": 3, "sofa_total": 2, "priority_weight": 1.0},
    ]
    mass = unserved_high_risk_mass(cands, assigned_stay_ids=[1])
    assert mass["uhrm"] == 3.0  # stay 2 unassigned high-risk
    assert mass["n_high_risk_pool"] == 2
    care = compute_care(
        high_risk_assigned=1,
        n_high_risk_pool=2,
        overload=10,
        uhrm=3.0,
        uhrm_pool_weight=7.0,
    )
    assert care["care_cover"] == 0.5
    assert care["care"] < 0.5
