"""Small-scale CP-SAT test with isolation beds & ventilator constraints."""
from ortools.sat.python import cp_model
import random

random.seed(42)
n_patients = 20
n_beds = 10
n_iso_beds = 2
n_vents = 5

patients = [
    {"id": i, "w": round(random.uniform(0.5, 3.0), 2), "iso": i < 3, "vent": i < 7}
    for i in range(n_patients)
]

model = cp_model.CpModel()

x = {}
for i in range(n_patients):
    for b in range(n_beds):
        x[i, b] = model.NewBoolVar(f"x_{i}_{b}")

for b in range(n_beds):
    model.Add(sum(x[i, b] for i in range(n_patients)) <= 1)
for i in range(n_patients):
    model.Add(sum(x[i, b] for b in range(n_beds)) <= 1)

# isolation: beds 0,1 are isolation beds
for i in range(n_patients):
    if patients[i]["iso"]:
        for b in range(n_iso_beds, n_beds):
            model.Add(x[i, b] == 0)
    else:
        for b in range(n_iso_beds):
            model.Add(x[i, b] == 0)

# ventilator limit
vent_use = []
for i in range(n_patients):
    if patients[i]["vent"]:
        vent_use.append(sum(x[i, b] for b in range(n_beds)))
if vent_use:
    model.Add(sum(vent_use) <= n_vents)

model.Maximize(
    sum(int(patients[i]["w"] * 100) * x[i, b] for i in range(n_patients) for b in range(n_beds))
)

solver = cp_model.CpSolver()
status = solver.Solve(model)
print(f"Status: {'OPTIMAL' if status == cp_model.OPTIMAL else status}")
print()

print(f"{'Pat':>4} {'Weight':>8} {'Iso':>4} {'Vent':>5} {'Bed':>4}")
for i in range(n_patients):
    for b in range(n_beds):
        if solver.Value(x[i, b]) == 1:
            p = patients[i]
            bed_type = "ISO" if b < n_iso_beds else "reg"
            print(f"{p['id']:>4} {p['w']:>8.2f} {'Y' if p['iso'] else '-':>4} {'Y' if p['vent'] else '-':>5} {b}({bed_type}):>4")

assigned = sum(
    1 for i in range(n_patients) for b in range(n_beds) if solver.Value(x[i, b]) == 1
)
print(f"\nAssigned: {assigned}/{n_beds} beds")
print(f"Objective: {solver.ObjectiveValue():.0f}")
print("TEST PASSED" if assigned > 0 else "TEST FAILED")
