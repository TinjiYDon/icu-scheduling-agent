from application.evaluate_ppo import _cp_sat_canonical, _enrich_policy_metrics
from domain.rl.env import Bed, ICUEnv, Patient


def _env() -> ICUEnv:
    patients = [
        Patient(stay_id=1, priority_weight=3.0, sofa_total=12.0, needs_isolation=True),
        Patient(stay_id=2, priority_weight=1.0, sofa_total=3.0),
        Patient(stay_id=3, priority_weight=2.0, sofa_total=11.0),
    ]
    beds = [
        Bed(bed_id=1, zone="ISO", is_isolation=True),
        Bed(bed_id=2, zone="SICU"),
    ]
    return ICUEnv(patients, beds)


def test_enrich_adds_canonical_fields():
    env = _env()
    env.reset(seed=0)
    env.step(0)  # patient 1 (SOFA 12, ISO) -> ISO bed
    env.step(env.wait_action)  # patient 2 (SOFA 3) waits
    env.step(env.wait_action)  # patient 3 (SOFA 11) high-risk, waits
    result = {
        "policy": "ppo",
        "assignments": list(env.assignments),
        "assigned": len(env.assignments),
        "n_stays": 3,
        "total_reward": -2.0,
    }

    enriched = _enrich_policy_metrics(env, result)

    assert enriched["episode_reward"] == -2.0
    # Two high-risk stays (SOFA >= 10); one was admitted, one waited.
    assert enriched["high_risk_wait"] == 1
    assert enriched["constraint_violations"] == 0


def test_enrich_counts_constraint_violations():
    env = _env()
    env.reset(seed=0)
    # Force an impossible assignment: ventilator patient on a non-vent bed.
    env.patients = [
        Patient(stay_id=9, priority_weight=1.0, sofa_total=12.0, needs_ventilator=True)
    ]
    env.assignments = [{"stay_id": 9, "bed_id": 2, "zone": "SICU"}]

    enriched = _enrich_policy_metrics(env, {"total_reward": 0.0})

    assert enriched["constraint_violations"] == 1


def test_cp_sat_canonical_aliases():
    canonical = _cp_sat_canonical({"high_risk_waiting": 187})
    assert canonical["high_risk_wait"] == 187
    assert canonical["constraint_violations"] == 0
    # Original keys are preserved for downstream consumers.
    assert canonical["high_risk_waiting"] == 187
