from domain.ops.h3_fair import (
    annotate_fair_report,
    fair_pool_note,
    resource_overrides_from_env,
    stay_ids_from_env,
)


class _P:
    def __init__(self, stay_id: int) -> None:
        self.stay_id = stay_id


class _Env:
    def __init__(self) -> None:
        self.patients = [_P(3), _P(7)]


def test_stay_ids_from_env():
    assert stay_ids_from_env(_Env()) == [3, 7]


def test_annotate_fair_report():
    report = annotate_fair_report({"status": "ok"}, stay_ids=[1, 2], n_beds=20)
    assert report["fair_pool"] is True
    assert report["shared_n_beds"] == 20
    assert "Fair H3" in fair_pool_note(2, 20)


class _Bed:
    def __init__(self, bed_id: int, zone: str, is_isolation: bool) -> None:
        self.bed_id = bed_id
        self.zone = zone
        self.is_isolation = is_isolation
        self.has_ventilator = True


class _ResEnv:
    def __init__(self) -> None:
        self.beds = [
            _Bed(1, "ISO", True),
            _Bed(2, "ISO", True),
            _Bed(3, "MICU", False),
            _Bed(4, "MICU", False),
        ]
        self.ventilator_capacity = 3


def test_resource_overrides_from_env_matches_layout():
    ov = resource_overrides_from_env(_ResEnv())
    assert ov["n_beds"] == 4
    assert ov["n_isolation_beds"] == 2
    assert ov["n_ventilators"] == 3
    assert ov["bed_zones"] == [[1, 2, "ISO"], [3, 2, "MICU"]]
    tagged = annotate_fair_report(
        {"status": "ok"}, stay_ids=[1], n_beds=4, resources=ov
    )
    assert tagged["shared_resources"]["n_isolation_beds"] == 2
