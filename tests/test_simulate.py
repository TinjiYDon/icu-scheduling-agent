def test_scheduling_modules_import():
    from domain.optimizer.cp_sat import run_assignment
    from domain.scoring.sofa import compute_sofa_timeseries

    assert callable(run_assignment)
    assert callable(compute_sofa_timeseries)
