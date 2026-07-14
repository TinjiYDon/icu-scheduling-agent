def test_plan_module_imports():
    from application.plan import get_plan, run_simulation_with_plan
    from data_access.assignments_repo import fetch_assignments, latest_run_id

    assert callable(get_plan)
    assert callable(run_simulation_with_plan)
    assert callable(fetch_assignments)
    assert callable(latest_run_id)


def test_get_plan_not_found():
    from application.plan import get_plan

    out = get_plan(run_id="__nonexistent_run__")
    assert out["assignments"] == []
    assert out["status"] == "not_found"
