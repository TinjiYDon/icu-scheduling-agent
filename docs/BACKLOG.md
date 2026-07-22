# 任务 Backlog

---

## S0 ✓

- [x] ETL + dump + 冒烟（A）

---

## S1 · SOFA

- [ ] **#S1-1** B：`domain/scoring/sofa.py` 写入 `feat.sofa_*`  
  - 验证：SQL 或 pytest 查 feat 行  
- [ ] **#S1-2** A：确认 ETL 输出含 SOFA 所需 vitals/labs

---

## S3 · Streamlit

- [x] **#S3-1** C：`presentation/streamlit_app.py` 展示状态 → 分配方案 ✅
  - L4：`application/plan.py` · 只调 L4

---

## S2 · CP-SAT 仿真（B + C）

- [ ] **#S2-1** B：`domain/optimizer/cp_sat.py` 20 床 demo（已有，待指标完善）
- [ ] **#S2-2** B：`application/simulate.py` 端到端
- [x] **#S2-3** C：`application/plan.py` + `data_access/assignments_repo.py` ✅
- [x] **#S3-1b** Streamlit 目标分解 metrics、`not_found` 状态 ✅

---

## S4 · 进阶

- [ ] **#S4-1** B：PPO stub（P3 · 保持 Draft PR #3）  
- [x] **#S4-2** C：MCP `optimize_beds`（骨架 ✅ 2026-07-22）

---

## 基础设施

- [ ] **#INF-1** A：pytest CI  
- [ ] **#INF-2** C：PR checklist
