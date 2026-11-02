"""FD 压测度量单元测试：纯函数，无数据库/求解器/网络。"""

import numpy as np
import pytest

from domain.optimizer.data_contract import ConstraintContract, FieldContract
from domain.optimizer.fd_stress import (
    KNOWN_FDS,
    field_alignment,
    make_synthetic_columns,
    ranking_stability,
    refusal_accuracy,
    spurious_dof,
)


def _naive_spec():
    return {
        "variables": [
            {"name": "x_priority", "fields": ["priority_weight", "sofa_total", "los_hours"]}
        ],
        "constraints": [
            {"name": "iso", "fields": ["isolation_heuristic", "first_careunit"]},
            {"name": "los", "fields": ["los_hours"]},
        ],
    }


def _audited_spec():
    return {
        "variables": [
            {"name": "x_priority", "fields": ["priority_weight"], "excluded": ["sofa_total"]}
        ],
        "constraints": [
            {"name": "iso", "fields": ["isolation_heuristic"]},
            {"name": "los", "fields": ["los_days"]},
        ],
    }


# 1 — spurious_dof -----------------------------------------------------------


def test_spurious_dof_counts_naive_model():
    # priority 与 sofa 同场（变量 1）+ isolation 与 careunit 同场（约束 1）
    # + los_hours 被直接当输入（约束 1）
    assert spurious_dof(_naive_spec(), KNOWN_FDS) == 3


def test_spurious_dof_audited_model_is_zero():
    assert spurious_dof(_audited_spec(), KNOWN_FDS) == 0
    # 显式剔除说明也能压掉变量层计数
    spec = {
        "variables": [
            {"name": "v", "fields": ["priority_weight", "sofa_total"], "redundancy_note": "dropped sofa"}
        ]
    }
    assert spurious_dof(spec, KNOWN_FDS) == 0


def test_spurious_dof_without_fds_is_zero():
    assert spurious_dof(_naive_spec(), {}) == 0
    assert spurious_dof({"variables": ["priority_weight"]}, {}) == 0


# 2 — field_alignment --------------------------------------------------------


def test_field_alignment_in_unit_interval():
    contracts = [
        FieldContract("priority_weight", "heuristic", depends_on=("sofa_total",)),
        FieldContract("los_hours", "unit_error"),
        FieldContract("isolation_heuristic", "heuristic"),
        FieldContract("first_careunit", "exact"),
    ]
    spec = {"variables": [{"fields": ["priority_weight", "los_hours"]}]}
    value = field_alignment(spec, contracts)
    assert 0.0 <= value <= 1.0
    assert value == pytest.approx(0.5)

    full = field_alignment({"variables": [{"fields": ["priority_weight"]}]}, contracts)
    assert full == pytest.approx(1.0)


def test_field_alignment_constraint_contract_counts_as_declared():
    contracts = [ConstraintContract("rank", ("priority_weight", "sofa_total"))]
    assert field_alignment({"constraints": [{"fields": ["sofa_total"]}]}, contracts) == 1.0


# 3 — refusal_accuracy -------------------------------------------------------


def test_refusal_accuracy_boundaries():
    hit = [{"action": "refuse"}, {"action": "degrade"}, {"action": "pass"}]
    assert refusal_accuracy(hit, [True, False, False]) == pytest.approx(1.0)
    assert refusal_accuracy(hit, [False, True, True]) == pytest.approx(0.0)
    assert refusal_accuracy([{"action": "refuse"}], [1]) == pytest.approx(1.0)


def test_refusal_accuracy_invalid():
    with pytest.raises(ValueError):
        refusal_accuracy([], [])
    with pytest.raises(ValueError):
        refusal_accuracy([{"action": "pass"}], [True, False])
    with pytest.raises(ValueError):
        refusal_accuracy([{"action": "maybe"}], [True])


# 4 — ranking_stability ------------------------------------------------------


def test_ranking_stability_boundaries():
    a = [0.9, 0.5, 0.4, 0.1]
    b = [0.9, 0.5, 0.4, 0.1]
    assert ranking_stability(a, b, k=3) == pytest.approx(1.0)

    disjoint = sorted(a)
    assert ranking_stability(a, disjoint, k=2) == pytest.approx(0.0)

    # k 超过长度时按 min(k, n) 归一
    assert ranking_stability(a, a, k=99) == pytest.approx(1.0)
    # 2-D 目标矩阵按行求和
    mat = [[1.0, 0.0], [0.0, 0.5]]
    assert ranking_stability(mat, [1.0, 0.5], k=2) == pytest.approx(1.0)


def test_ranking_stability_invalid():
    with pytest.raises(ValueError):
        ranking_stability([], [0.1])
    with pytest.raises(ValueError):
        ranking_stability([0.1], [0.1], k=0)
    with pytest.raises(ValueError):
        ranking_stability([0.1, float("nan")], [0.1, 0.2])
    with pytest.raises(ValueError):
        ranking_stability([[0.1, 0.2], [0.3]], [0.1, 0.2])


# 5 — 合成列与非法输入 -------------------------------------------------------


def test_make_synthetic_columns_contracts():
    cols = make_synthetic_columns(n=50, seed=7)
    assert set(cols) == {
        "stay_id",
        "sofa_total",
        "priority_weight",
        "los_hours",
        "first_careunit",
        "isolation_heuristic",
    }
    assert len(cols["stay_id"]) == 50
    for sofa, prio, los in zip(cols["sofa_total"], cols["priority_weight"], cols["los_hours"]):
        assert prio == pytest.approx(1.0 + sofa / 10.0)
        assert float(los).is_integer() and 1 <= los <= 14  # 实为天数
    assert set(cols["isolation_heuristic"]) <= {0, 1}

    again = make_synthetic_columns(n=50, seed=7)
    assert again == cols
    with pytest.raises(ValueError):
        make_synthetic_columns(n=0, seed=0)
    with pytest.raises(ValueError):
        make_synthetic_columns(n=10, seed="x")


def test_invalid_model_specs_and_contracts():
    with pytest.raises(ValueError):
        spurious_dof({}, KNOWN_FDS)
    with pytest.raises(ValueError):
        spurious_dof({"variables": [], "constraints": []}, KNOWN_FDS)
    with pytest.raises(ValueError):
        spurious_dof(_naive_spec(), ["priority_weight"])
    with pytest.raises(ValueError):
        spurious_dof({"variables": [{"fields": "priority_weight"}], "extra": 1}, KNOWN_FDS)
    with pytest.raises(ValueError):
        field_alignment(_naive_spec(), [{"name": "x"}])
    with pytest.raises(ValueError):
        field_alignment(_naive_spec(), [])


def test_numpy_inputs_supported():
    cols = make_synthetic_columns(n=5, seed=1)
    spec = {"variables": [{"fields": ["priority_weight", "sofa_total"]}]}
    assert spurious_dof(spec, {"priority_weight": np.array(["sofa_total"])}) == 1
    assert refusal_accuracy([{"action": "pass"}], np.array([False])) == 1.0
    assert 0.0 <= field_alignment(spec, [FieldContract("sofa_total", "exact")]) <= 1.0
    assert cols["sofa_total"] == [int(x) for x in cols["sofa_total"]]
