# 任务 Backlog

---

## S0 ✓

- [x] ETL + dump + 冒烟（A）

---

## S1 · SOFA

- [x] **#S1-1** B：`domain/scoring/sofa.py` 写入 `feat.sofa_*`（STATUS 已有真实 SOFA ✅）
- [x] **#S1-2** A：ETL/labs + full dump（Owner dump 20260727 ✅）

---

## S3 · Streamlit

- [x] **#S3-1** C：`presentation/streamlit_app.py` 展示状态 → 分配方案 ✅
  - L4：`application/plan.py` · 只调 L4

---

## S2 · CP-SAT 仿真（B + C）

- [x] **#S2-1** B：`domain/optimizer/cp_sat.py` 20 床 demo ✅
- [x] **#S2-2** B：`application/simulate.py` 端到端 + STATUS 数值（**Wave2** ✅ 2026-07-31）
- [x] **#S2-3** C：`application/plan.py` + `data_access/assignments_repo.py` ✅
- [x] **#S2-3b** C：calib/eval 骨架 + metrics 键（**Wave1** ✅ 2026-07-25）
- [x] **#S3-1b** Streamlit 目标分解 metrics、`not_found` 状态 ✅

---

## S4 · 进阶

- [x] **#S4-1a** B：PPO/lambda 代码入 main（PR #3 ✅ 2026-07-30 · 默认仍 cp_sat）
- [ ] **#S4-1b** B：MIMIC `sim` 轨迹包 + 真训（**未交付** · 见 `PPO_SMOKE.md`）
- [x] **#S4-2** C：MCP `optimize_beds`（骨架 ✅ 2026-07-22）

---

## 基础设施

- [x] **#INF-1** A：pytest CI（`.github/workflows/ci.yml` ✅）
- [x] **#INF-2** C：PR checklist（`.github/pull_request_template.md` ✅）
