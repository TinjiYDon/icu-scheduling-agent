"""Quick test: CP-SAT with limited patients (100)."""
from __future__ import annotations
from infra.db import get_engine
from infra.config import load_yaml
from sqlalchemy import text
from ortools.sat.python import cp_model

opt = load_yaml("optimizer.yaml")
n_beds = int(opt.get("resources", {}).get("n_beds", 20))

engine = get_engine()
with engine.connect() as conn:
    rows = conn.execute(text("""
        SELECT s.stay_id, COALESCE(p.priority_weight, 1.0) AS w
        FROM staging.icustays s
        LEFT JOIN feat.patient_priority p ON s.stay_id = p.stay_id
        ORDER BY w DESC
        LIMIT 100
    """)).mappings().all()

stays = [dict(r) for r in rows]
n = len(stays)
print(f"Patients: {n}, Beds: {n_beds}")

model = cp_model.CpModel()
x = {}
for si in range(n):
    for bi in range(n_beds):
        x[si, bi] = model.NewBoolVar(f"x_{si}_{bi}")

for bi in range(n_beds):
    model.Add(sum(x[si, bi] for si in range(n)) <= 1)
for si in range(n):
    model.Add(sum(x[si, bi] for bi in range(n_beds)) <= 1)

weights = [int(float(s["w"]) * 1000) for s in stays]
model.Maximize(sum(weights[si] * x[si, bi] for si in range(n) for bi in range(n_beds)))

solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = 10.0
status = solver.Solve(model)

assigned = sum(1 for si in range(n) for bi in range(n_beds) if solver.Value(x[si, bi]) == 1)
print(f"Status: {status}, Assigned: {assigned}/{n_beds}")
print(f"Objective: {solver.ObjectiveValue():.0f}")
print("CP-SAT test: PASSED" if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else "CP-SAT test: FAILED")
