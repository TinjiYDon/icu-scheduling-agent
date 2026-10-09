# Merge 门槛 · 对齐最终目标（scheduling）

> 2026-09-24 · 与 decision [`MERGE_GATE`](https://github.com/TinjiYDon/icu-decision-agent/blob/main/docs/MERGE_GATE.md) 同准则

## 已合入创新主线

| PR | 贡献 |
|----|------|
| [#10](https://github.com/TinjiYDon/icu-scheduling-agent/pull/10) | **S2-MOO（H4）** 三种多目标机理 |
| [#11](https://github.com/TinjiYDon/icu-scheduling-agent/pull/11) | Fair H3 + 阶段 5 UI + ε 重标定 + CI test_plan |
| [#12](https://github.com/TinjiYDon/icu-scheduling-agent/pull/12) | H3 同资源布局 + L4 `moo_ui`/`h3_ui` + restore recreate |

## 合入优先序（下一拍）

| 优先 | 项 | 为何 |
|------|-----|------|
| ✅ | **S2-TRAJ** 轨迹导出验收 | 2026-09-24 已过；仍禁虚假 online 宣称 |
| ✅ | MOO 阶段 2 指标语义 | acuity `overload` + `priority_served` 披露 |
| ✅ | MOO 阶段 3 ε 网格 / payoff | A2 calib：81/54/4 · HV=0.038794 |
| ✅ | MOO 阶段 4 六场景 | 轻量 WS+Lex+ε；WS/Lex 全 OPTIMAL |
| ✅ | MOO 阶段 5 Streamlit | PR #11「多目标」+「对照」 |
| ✅ | H3 资源布局对齐 follow-up | PR #12 |
| ✅ | S3 同池多 episode 深化 | fair benchmark + 对照页 Tab |
| ✅ | 老师演示清单 | `DEMO_SCRIPT.md` 对齐多目标/对照 |

## 已关闭

- #9 docs nightly cleanup（无创新产出）
