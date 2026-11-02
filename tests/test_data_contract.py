"""AIGC 语义可用性契约（DAC）单元测试：纯函数，无数据库/求解器/网络。"""

import pytest

from domain.optimizer.data_contract import (
    AVAILABILITY_LEVELS,
    ConstraintContract,
    ContractReport,
    FieldContract,
    check_contract,
    contract_from_dicts,
    degrade_or_refuse,
)


def _basic_contracts():
    fields = [
        FieldContract("sofa_total", "exact"),
        FieldContract("priority_weight", "heuristic", depends_on=("sofa_total",)),
        FieldContract("first_careunit", "exact"),
        FieldContract(
            "isolation_heuristic",
            "heuristic",
            depends_on=("first_careunit",),
            redundant_with=("first_careunit",),
        ),
    ]
    constraints = [ConstraintContract("priority_rank", ("priority_weight",), "错误排序")]
    return fields, constraints


# 1 — 可用级别与合法通过 ------------------------------------------------------


def test_availability_levels_declared():
    assert AVAILABILITY_LEVELS == (
        "exact",
        "proxy",
        "heuristic",
        "stale",
        "unit_error",
        "missing",
    )


def test_valid_contract_passes():
    fields, constraints = _basic_contracts()
    fields = [f for f in fields if f.name != "isolation_heuristic"]
    report = check_contract(fields + constraints, ["sofa_total", "priority_weight"], {})
    assert isinstance(report, ContractReport)
    assert report.ok is True
    assert report.violations == ()
    assert report.action == "pass"
    assert degrade_or_refuse(report)["action"] == "pass"


# 2 — 缺字段 → refuse --------------------------------------------------------


def test_missing_constraint_field_refuses():
    fields, constraints = _basic_contracts()
    report = check_contract(fields + constraints, ["sofa_total"], {})
    assert report.ok is False
    assert report.action == "refuse"
    assert any("priority_weight" in v for v in report.violations)
    assert any("priority_rank" in v for v in report.violations)
    assert degrade_or_refuse(report, policy="advisory")["action"] == "refuse"


def test_missing_availability_level_refuses_even_if_column_present():
    contracts = [
        FieldContract("los_hours", "unit_error"),
        FieldContract("gbdt_pred", "missing"),
    ]
    report = check_contract(contracts, ["los_hours", "gbdt_pred"], {})
    assert report.action == "refuse"
    assert len(report.violations) == 2


# 3 — 冗余字段 → degrade -----------------------------------------------------


def test_redundant_field_degrades_not_refuses():
    fields, constraints = _basic_contracts()
    columns = ["priority_weight", "sofa_total", "isolation_heuristic", "first_careunit"]
    report = check_contract(fields + constraints, columns, {})
    assert report.action == "degrade"
    assert report.ok is False
    joined = " | ".join(report.violations)
    assert "redundant" in joined or "冗余" in joined


def test_fd_map_redundancy_detected_without_field_contract():
    report = check_contract(
        [ConstraintContract("rank", ("priority_weight",))],
        {"priority_weight": [1.1], "sofa_total": [10]},
        {"priority_weight": ("sofa_total",)},
    )
    assert report.action == "degrade"
    assert any("函数依赖" in v for v in report.violations)


# 4 — strict 强制 refuse / 三档策略 -----------------------------------------


def test_strict_policy_forces_refuse_on_degrade():
    fields, constraints = _basic_contracts()
    columns = ["priority_weight", "sofa_total", "isolation_heuristic", "first_careunit"]
    report = check_contract(fields + constraints, columns, {})
    assert report.action == "degrade"

    strict = degrade_or_refuse(report, policy="strict")
    assert strict["action"] == "refuse"
    assert "strict" in strict["reason"]

    advisory = degrade_or_refuse(report, policy="advisory")
    assert advisory["action"] == "degrade"

    lenient = degrade_or_refuse(report, policy="lenient")
    assert lenient["action"] == "degrade"


# 5 — 非法输入 ---------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"contracts": [], "columns": ["a"], "fd_map": {}},
        {"contracts": [FieldContract("a", "exact")], "columns": [], "fd_map": {}},
        {"contracts": [FieldContract("a", "exact")], "columns": "abc", "fd_map": {}},
        {"contracts": [FieldContract("a", "exact")], "columns": ["a"], "fd_map": []},
        {"contracts": [{"name": "c", "fields": ["a"]}], "columns": ["a"], "fd_map": {}},
        {"contracts": [ConstraintContract("c", ("a",))], "columns": [1], "fd_map": {}},
    ],
)
def test_check_contract_invalid_inputs(kwargs):
    with pytest.raises(ValueError):
        check_contract(**kwargs)


def test_field_contract_rejects_bad_level_and_empty_dep():
    with pytest.raises(ValueError):
        FieldContract("a", "sometimes")
    with pytest.raises(ValueError):
        FieldContract("a", "exact", depends_on=("",))


def test_report_and_policy_validation():
    with pytest.raises(ValueError):
        ContractReport(ok=False, violations=("x",), action="maybe")
    report = ContractReport(ok=False, violations=("x",), action="degrade")
    with pytest.raises(ValueError):
        degrade_or_refuse(report, policy="yolo")
    with pytest.raises(ValueError):
        degrade_or_refuse({"action": "pass"})


# 6 — contract_from_dicts ----------------------------------------------------


def test_contract_from_dicts():
    contracts = contract_from_dicts(
        [
            {"name": "iso", "fields": ["isolation_heuristic"], "failure_mode": "漏隔离"},
            {"name": "los", "fields": ["los_hours", "n_beds"]},
        ]
    )
    assert isinstance(contracts, tuple)
    assert all(isinstance(c, ConstraintContract) for c in contracts)
    assert contracts[0].failure_mode == "漏隔离"
    assert contracts[1].fields == ("los_hours", "n_beds")

    with pytest.raises(ValueError):
        contract_from_dicts([])
    with pytest.raises(ValueError):
        contract_from_dicts([{"name": "x"}])
    with pytest.raises(ValueError):
        contract_from_dicts([{"name": "x", "fields": ["a"], "priority": 1}])
    with pytest.raises(ValueError):
        contract_from_dicts({"name": "x", "fields": ["a"]})


def test_contracts_accept_mapping_bundle():
    bundle = {
        "fields": [FieldContract("sofa_total", "exact")],
        "constraints": [ConstraintContract("c", ("sofa_total",))],
    }
    report = check_contract(bundle, ["sofa_total"], {})
    assert report.ok is True
