from domain.optimizer.resources import layout_covers_beds, scale_bed_layout


def test_scale_bed_layout_sums_to_n():
    for n in (5, 10, 20, 22, 30, 40):
        layout = scale_bed_layout(n)
        assert layout["n_beds"] == n
        assert layout_covers_beds(layout["bed_zones"], n)
        assert layout["n_isolation_beds"] >= 1
        assert layout["n_isolation_beds"] <= n


def test_default_20_matches_template():
    layout = scale_bed_layout(20)
    assert layout["n_isolation_beds"] == 4
    assert layout["bed_zones"][0] == [1, 4, "ISO"]
