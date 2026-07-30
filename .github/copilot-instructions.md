# Copilot / Agent instructions — icu-scheduling-agent

- Default optimizer: CP-SAT (`configs/optimizer.yaml` policy.default)
- L4: `application.plan` only from Streamlit
- Test: `pytest tests/test_plan.py -q` with `PYTHONPATH=.`
- PPO/MaskablePPO stays on Draft PR until reviewed; do not enable as default
- Read `docs/PARAM_STORY.md` for SOFA/priority/lambda meanings
- Do not commit dumps/artifacts
