def test_plan_module_imports():
    from application.plan import get_plan, run_simulation_with_plan

    assert callable(get_plan)
    assert callable(run_simulation_with_plan)


def test_get_plan_empty_ok():
    from application.plan import get_plan

    out = get_plan(run_id="__nonexistent_run__")
    assert out["assignments"] == []
