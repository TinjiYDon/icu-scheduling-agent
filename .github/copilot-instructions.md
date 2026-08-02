# Copilot / Agent instructions — icu-scheduling-agent

- Default optimizer: CP-SAT (`configs/optimizer.yaml` policy.default)
- L4: `application.plan` only from Streamlit
- Test: `pytest tests/test_plan.py -q` with `PYTHONPATH=.`
- PPO/MaskablePPO code is on main (PR #3 merged); keep `policy.default: cp_sat`; no MIMIC trajectory package yet
- Read `docs/PARAM_STORY.md` for SOFA/priority/lambda meanings
- Do not commit dumps/artifacts
