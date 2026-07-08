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

## S2 · CP-SAT 仿真

- [ ] **#S2-1** B：`domain/optimizer/cp_sat.py` 20 床 demo  
- [ ] **#S2-2** B：`application/simulate.py` 端到端  
  - 验证：`python -m application.simulate`  
  - 测试：`tests/test_simulate.py`

---

## S3 · Streamlit

- [ ] **#S3-1** C：展示状态输入 → 分配方案 → 目标分解  
  - 只调 L4

---

## S4 · 进阶

- [ ] **#S4-1** B：PPO stub（P3）  
- [ ] **#S4-2** C：MCP `optimize_beds`（P2）

---

## 基础设施

- [ ] **#INF-1** A：pytest CI  
- [ ] **#INF-2** C：PR checklist
