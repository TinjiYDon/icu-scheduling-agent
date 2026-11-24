"""调度实验只读校验：不改任何文件，只打印结论。

用法：
  python experiments/scheduling/src/verify.py --tag _g1

检查项
  1. 每个 (场景, 方法) 一行摘要（episode 行数、等待、收益、搬移/挤出、求解耗时）
  2. episode csv 行数 ≈ 4296（4380 步 − 7 天 warmup 84 步）
  3. 所有方法 displaced == 0（在科病人不被挤出）
  4. 每条轨迹的隔离床占用 ≤ 5、呼吸机设备占用 ≤ 8（硬约束未被突破）
  5. benefit_served(method) ≤ 场景总收益；且跨方法求和 ≤ 方法数 × 总收益（防重复计数）
  6. metrics_sched.json 的每负荷均值与 table_sched.csv 一致（容差 1e-6）
  7. SECTION.md 里引用的数字能在 csv/json 中找到（找不到只 warning，不 hard fail）

全部通过时打印 ALL CHECKS PASSED。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

SRC = Path(__file__).resolve().parent
ROOT = SRC.parent                      # experiments/scheduling
DATA = ROOT / "data"
RES = ROOT / "results"
N_STEPS = 4380
WARMUP_STEPS = 84
EXPECT_ROWS = N_STEPS - WARMUP_STEPS   # 4296
N_ISO = 5
N_VENTS = 8
TOL = 1e-6
SECTION = ROOT / "SECTION.md"

FAILS: list[str] = []
WARNS: list[str] = []


def fail(msg: str) -> None:
    FAILS.append(msg)
    print(f"  [FAIL] {msg}")


def warn(msg: str) -> None:
    WARNS.append(msg)
    print(f"  [WARN] {msg}")


def ok(msg: str) -> None:
    print(f"  [ok]   {msg}")


# ─────────────────────── 1. 逐 (场景, 方法) 摘要 ───────────────────────
def check_episodes(df: pd.DataFrame, tag: str) -> dict[tuple[str, str], int]:
    print(f"\n[1] 逐场景逐方法摘要（tag={tag}）")
    print(f"{'scenario':22s} {'method':18s} {'rows':>5s} {'hr_wait':>8s} {'within6':>7s} "
          f"{'queue':>6s} {'benefit':>8s} {'moved':>5s} {'displ':>5s} {'ms/dec':>7s}")
    rows: dict[tuple[str, str], int] = {}
    for r in df.sort_values(["scenario", "method"]).itertuples():
        p = RES / "episodes" / f"{r.scenario}__{r.method}{tag}.csv"
        n = -1
        if p.exists():
            tr = pd.read_csv(p)
            n = len(tr)
            rows[(r.scenario, r.method)] = n
        print(f"{r.scenario:22s} {r.method:18s} {n:5d} {r.hr_wait_mean:8.3f} "
              f"{r.hr_within6:7.3f} {r.avg_queue:6.2f} {r.benefit_served:8.1f} "
              f"{int(r.moved):5d} {int(r.displaced):5d} {r.solve_ms_mean:7.1f}")
    return rows


# ─────────────────────── 2. 轨迹长度 ───────────────────────
def check_trace_len(rows: dict[tuple[str, str], int]) -> None:
    print(f"\n[2] episode 行数 == {EXPECT_ROWS}（4380 - 84 warmup）")
    bad = {k: v for k, v in rows.items() if v != EXPECT_ROWS}
    missing = [k for k in rows if rows[k] < 0]
    if missing:
        fail(f"{len(missing)} 个 episode csv 缺失：{missing[:5]}")
    if bad:
        fail(f"{len(bad)} 个 episode 行数异常：{list(bad.items())[:5]}")
    elif not missing:
        ok(f"全部 {len(rows)} 条轨迹行数 = {EXPECT_ROWS}")


# ─────────────────────── 3. displaced == 0 ───────────────────────
def check_displaced(df: pd.DataFrame) -> None:
    print("\n[3] 在科病人挤出次数 displaced == 0")
    bad = df[df["displaced"] != 0]
    if len(bad):
        fail(f"{len(bad)} 次运行 displaced != 0："
             f"{bad[['scenario', 'method', 'displaced']].head(8).to_dict('records')}")
    else:
        ok(f"全部 {len(df)} 次运行 displaced = 0")


# ─────────────────────── 4. 硬约束未被突破 ───────────────────────
def check_hard_constraints(tag: str) -> None:
    print(f"\n[4] 轨迹级硬约束：隔离床 ≤ {N_ISO}、呼吸机设备 ≤ {N_VENTS}")
    n_file, bad = 0, []
    for p in sorted((RES / "episodes").glob(f"*{tag}.csv")):
        tr = pd.read_csv(p)
        n_file += 1
        if "iso_used" in tr and tr["iso_used"].max() > N_ISO:
            bad.append((p.name, "iso", int(tr["iso_used"].max())))
        if "vent_devices" in tr and tr["vent_devices"].max() > N_VENTS:
            bad.append((p.name, "vent", int(tr["vent_devices"].max())))
        if "occupancy" in tr and tr["occupancy"].max() > 20:
            bad.append((p.name, "occupancy", int(tr["occupancy"].max())))
    if bad:
        fail(f"{len(bad)} 处越界：{bad[:5]}")
    elif n_file == 0:
        warn("没有找到轨迹文件")
    else:
        ok(f"{n_file} 条轨迹：隔离/呼吸机/床位占用均未越界")


# ─────────────────────── 5. benefit 上界 ───────────────────────
def check_benefit(df: pd.DataFrame) -> None:
    print("\n[5] benefit_served 上界（同场景跨方法不得重复计数）")
    tot = {}
    for p in sorted(DATA.glob("scenario_*.json")):
        if p.name == "scenario_meta.json":
            continue
        sc = json.loads(p.read_text(encoding="utf-8"))
        tot[sc["name"]] = float(sum(x["benefit"] for x in sc["patients"]))
    bad = []
    for sc, g in df.groupby("scenario"):
        if sc not in tot:
            warn(f"{sc} 无对应 scenario json，跳过")
            continue
        total = tot[sc]
        for r in g.itertuples():
            if r.benefit_served > total + 1e-6:
                bad.append((sc, r.method, r.benefit_served, total))
        s = g["benefit_served"].sum()
        if s > len(g) * total + 1e-6:
            bad.append((sc, "SUM_ALL_METHODS", s, len(g) * total))
        # 说明性输出：单方法占场景总收益的比例
        print(f"  {sc:22s} total={total:9.1f} "
              f"served_ratio=" + " ".join(
                  f"{r.method.split('_')[0]}:{r.benefit_served / total:.3f}"
                  for r in g.itertuples()))
    if bad:
        fail(f"{len(bad)} 处 benefit 越界：{bad[:5]}")
    else:
        ok("每方法 benefit_served ≤ 场景总收益；跨方法求和 ≤ 方法数 × 总收益")


# ─────────────────────── 6. metrics_sched.json 一致性 ───────────────────────
def check_metrics(table: pd.DataFrame) -> None:
    # table_sched.csv 由 agg() 做 .round(4)，因此与 JSON 全精度值的最大差就是半个末位（5e-5）。
    # 用 1e-6 去比一定失败（那是"未四舍五入"才成立的容差）；这里改成
    #   ① 严格：round(json均值, 4) 必须逐位等于表里的值；
    #   ② 数值：|json - table| <= 5.1e-5（四舍五入的半个末位 + 余量）。
    TOL_TABLE = 5.1e-5
    print(f"\n[6] metrics_sched.json 均值 vs table_sched.csv"
          f"（表为 4 位小数：严格 round 一致 + |Δ| ≤ {TOL_TABLE:g}）")
    mp = RES / "metrics_sched.json"
    if not mp.exists():
        fail("metrics_sched.json 不存在，先跑 aggregate.py")
        return
    js = json.loads(mp.read_text(encoding="utf-8"))
    per_load = js.get("per_load", {})
    metrics = ["hr_wait_mean", "hr_within6", "wait_mean", "avg_queue",
               "utilization", "gini_hr_wait"]
    bad, n, maxdiff = [], 0, 0.0
    for load_s, methods in per_load.items():
        load = int(load_s)
        for meth, mvals in methods.items():
            row = table[(table["load"] == load) & (table["method"] == meth)]
            if row.empty:
                bad.append((load, meth, "missing_in_table", None, None))
                continue
            for m in metrics:
                if m not in mvals:
                    continue
                jv = float(mvals[m]["mean"])
                col = f"{m}_mean"
                if col not in row:
                    bad.append((load, meth, m, jv, "no_column"))
                    continue
                tv = float(row.iloc[0][col])
                n += 1
                maxdiff = max(maxdiff, abs(jv - tv))
                if round(jv, 4) != tv or abs(jv - tv) > TOL_TABLE:
                    bad.append((load, meth, m, jv, tv))
    if bad:
        fail(f"{len(bad)} 处不一致（前 5）：{bad[:5]}")
    else:
        ok(f"{n} 个 (负荷, 方法, 指标) 均值一致（最大 |Δ| = {maxdiff:.2e}，"
           f"来自表格 4 位小数的舍入）")

    # 每负荷每方法必须有 3 个种子
    cnt = js.get("per_load", {})
    bad_n = [(load, meth, mv["hr_wait_mean"]["n"])
             for load, d in cnt.items() for meth, mv in d.items()
             if mv.get("hr_wait_mean", {}).get("n") != 3]
    if bad_n:
        warn(f"种子数不为 3 的组合：{bad_n[:6]}")
    else:
        ok(f"每负荷每方法均为 3 个种子（{len(cnt)} 负荷 × "
           f"{len(next(iter(cnt.values())))} 方法）")


# ─────────────────────── 7. SECTION 数字可溯源 ───────────────────────
def _num_tokens(text: str) -> list[str]:
    """抽取值得核对的数字：带小数点的，或 ≥3 位整数。"""
    toks = re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w])", text)
    out = []
    for t in toks:
        if "." in t or len(t.lstrip("-")) >= 3:
            out.append(t)
    return out


def _known_values() -> set[str]:
    """把 csv/json 里的数值展开成 1/2/3 位小数的字符串集合，含百分比形式。"""
    vals: set[str] = set()
    files = list(RES.glob("*.csv")) + list(RES.glob("episodes/*.csv")) + list(RES.glob("*.json"))
    for p in files:
        try:
            if p.suffix == ".json":
                df = pd.json_normalize(json.loads(p.read_text(encoding="utf-8")))
            else:
                df = pd.read_csv(p, low_memory=False)
        except Exception:
            continue
        for c in df.columns:
            s = pd.to_numeric(df[c], errors="coerce").dropna()
            for v in s.to_numpy():
                fv = float(v)
                for nd in (0, 1, 2, 3, 4):
                    vals.add(f"{fv:.{nd}f}")
                if 0 <= fv <= 1.5:  # 比例 → 百分比
                    for nd in (0, 1, 2):
                        vals.add(f"{fv * 100:.{nd}f}")
                if 0 <= fv <= 150:  # 百分数 → 比例
                    vals.add(f"{fv / 100:.4f}")
    return vals


def check_section() -> None:
    print("\n[7] SECTION.md 引用数字可溯源（找不到只 warning）")
    if not SECTION.exists():
        warn("SECTION.md 尚不存在，跳过数字溯源")
        return
    text = SECTION.read_text(encoding="utf-8")
    body = re.sub(r"```.*?```", "", text, flags=re.S)  # 代码块不核
    known = _known_values()
    toks = _num_tokens(body)
    uniq = sorted(set(toks))
    miss = [t for t in uniq if t not in known
            and f"{float(t):.1f}" not in known
            and f"{float(t):.2f}" not in known
            and f"{float(t):.3f}" not in known]
    print(f"  数字 token {len(toks)} 个（去重 {len(uniq)}），可溯源 {len(uniq) - len(miss)} 个")
    if miss:
        warn(f"{len(miss)} 个数字未在 csv/json 中直接命中（可能是四舍五入/派生量）："
             f"{miss[:20]}")
    else:
        ok("SECTION 中所有数字均可在产物文件中找到")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="_g1")
    args = ap.parse_args()
    bench = RES / f"bench_raw{args.tag}.csv"
    table = RES / "table_sched.csv"
    print(f"=== 调度实验校验 (tag={args.tag}) ===")
    if not bench.exists():
        print(f"[FAIL] 缺少 {bench.name}，先跑 run_bench.py")
        sys.exit(1)
    df = pd.read_csv(bench)
    print(f"bench_raw: {len(df)} 次运行，{df['scenario'].nunique()} 场景 × "
          f"{df['method'].nunique()} 方法")

    rows = check_episodes(df, args.tag)
    check_trace_len(rows)
    check_displaced(df)
    check_hard_constraints(args.tag)
    check_benefit(df)
    if table.exists():
        check_metrics(pd.read_csv(table))
    else:
        fail("table_sched.csv 不存在，先跑 aggregate.py")
    check_section()

    print("\n" + "=" * 62)
    if FAILS:
        print(f"FAILED: {len(FAILS)} 项失败，{len(WARNS)} 项警告")
        for f in FAILS:
            print(f"  - {f}")
        sys.exit(1)
    if WARNS:
        print(f"通过（{len(WARNS)} 项 warning，见上）")
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
