from domain.ops.h3_fair import annotate_fair_report, fair_pool_note, stay_ids_from_env


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
