from domain.optimizer.moo_epsilon_recal import scenario_epsilon_bounds
from types import SimpleNamespace


def test_scenario_epsilon_bounds_scales_with_beds():
    s2 = SimpleNamespace(
        id="S2_bed_shortage",
        pool="default",
        resource_overrides={"n_beds": 12},
    )
    bounds = scenario_epsilon_bounds(s2)
    assert bounds["occupancy"] <= 6
    assert bounds["overload"] >= 120


def test_high_sofa_pool_bounds():
    s5 = SimpleNamespace(
        id="S5_high_sofa",
        pool="high_sofa",
        resource_overrides={},
    )
    bounds = scenario_epsilon_bounds(s5)
    assert bounds["occupancy"] <= 5
    assert bounds["overload"] >= 80
