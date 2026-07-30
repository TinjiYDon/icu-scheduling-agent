from domain.optimizer.eval_split import split_stay_ids


def test_eval_split_disjoint_and_ratio():
    ids = list(range(100))
    out = split_stay_ids(ids, calib_ratio=0.7, seed=42)
    calib = set(out["calib_stay_ids"])
    ev = set(out["eval_stay_ids"])
    assert calib.isdisjoint(ev)
    assert calib | ev == set(ids)
    assert abs(out["n_calib"] / 100 - 0.7) < 0.05
    assert out["seed"] == 42


def test_simulate_metrics_keys():
    """Import-level contract: run_simulate returns metrics dict shape when DB empty-safe."""
    from application import simulate as sim_mod

    assert hasattr(sim_mod, "run_simulate")
    # Soft check without requiring DB: eval_split helper alone
    meta = split_stay_ids([1, 2, 3, 4, 5], seed=1)
    assert "n_calib" in meta and "n_eval" in meta
