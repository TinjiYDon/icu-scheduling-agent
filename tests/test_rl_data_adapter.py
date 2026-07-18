from __future__ import annotations

from domain.rl.data_adapter import patient_from_row


def test_patient_adapter_matches_cp_sat_derived_attributes():
    patient = patient_from_row(
        {
            "stay_id": 123,
            "priority_weight": 2.5,
            "sofa_total": 11,
            "first_careunit": "Medical Intensive Care Unit (MICU)",
        }
    )

    assert patient.stay_id == 123
    assert patient.priority_weight == 2.5
    assert patient.sofa_total == 11
    assert patient.preferred_zone == "MICU"
    assert patient.needs_isolation is True
