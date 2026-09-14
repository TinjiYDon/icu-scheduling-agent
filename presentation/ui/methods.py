"""方法 — 调度项目正式方法说明。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from infra.config import load_yaml
from presentation.ui.theme import disclaimer

ROOT = Path(__file__).resolve().parents[2]


def render_methods() -> None:
    st.title("方法")
    st.caption("问题定义 · 数据 · 流程 · CP-SAT 与 PPO · 超参")

    opt = load_yaml("optimizer.yaml")
    res = opt.get("resources") or {}
    lam = opt.get("lambda") or {}
    ppo = opt.get("ppo") or {}

    st.header("1. 问题定义")
    st.markdown(
        "在有限床位、隔离床与呼吸机等资源约束下，为排队中的 ICU 候选患者分配床位，"
        "在优先级、负载均衡与科室匹配等目标之间进行权衡，并支持滚动时域仿真评估占用演化。"
        "运行台可调整床位数：分区与隔离床按比例自动扩缩，求解在硬约束可行时铺满床位。"
    )

    st.header("2. 数据")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "数据集": "住院候选池",
                    "存储位置": "staging.icustays",
                    "规模": "约 94,458 stays",
                    "含义": "可参与分配的 ICU 住院",
                },
                {
                    "数据集": "SOFA",
                    "存储位置": "feat.sofa_timeseries",
                    "规模": "与 stays 对齐",
                    "含义": "病情严重度（常用 hour_index=0）",
                },
                {
                    "数据集": "优先级",
                    "存储位置": "feat.patient_priority",
                    "规模": "与 stays 对齐",
                    "含义": "分配优先级权重",
                },
                {
                    "数据集": "求解实例",
                    "存储位置": "运行时截断",
                    "规模": f"最多 {res.get('max_patients', 200)} 名候选",
                    "含义": "按优先级与 SOFA 排序后的优化输入",
                },
                {
                    "数据集": "校准子集 calib",
                    "存储位置": "eval_split（stay_id）",
                    "规模": "约 70%",
                    "含义": "目标权重网格搜索",
                },
                {
                    "数据集": "评价子集 eval",
                    "存储位置": "eval_split（stay_id）",
                    "规模": "约 30%",
                    "含义": "独立评价，不回写调参",
                },
                {
                    "数据集": "PPO 训练环境",
                    "存储位置": "domain/rl + artifacts/ppo_icu.zip",
                    "规模": f"{ppo.get('training_pool_patients', 200)} 患者池 · "
                    f"{ppo.get('inference_n_beds', 20)} 床",
                    "含义": "序贯选床仿真；观测维度与训练床位数绑定",
                },
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.header("3. 处理与求解流程")
    st.graphviz_chart(
        """
        digraph {
          rankdir=LR;
          node [shape=box, style="rounded,filled", fillcolor="#f8fafc", color="#0f766e"];
          A [label="MIMIC 衍生表"];
          B [label="SOFA / 优先级"];
          C [label="候选截断"];
          D [label="CP-SAT 分配"];
          E [label="滚动仿真"];
          F [label="PPO 推理"];
          G [label="运行台"];
          A -> B -> C -> D -> E -> G;
          C -> F -> G;
        }
        """
    )

    st.header("4. 算法")
    left, right = st.columns(2)
    with left:
        st.subheader("4.1 CP-SAT（默认）")
        st.markdown(
            "基于 OR-Tools 的约束规划求解。"
            "决策变量表示患者—床位匹配；硬约束包括床位容量、隔离床与呼吸机等。"
        )
        st.markdown("**加权多目标（示意）**")
        st.latex(
            r"\max\;"
            r"\lambda_w f_{\mathrm{priority}}"
            r"- \lambda_o f_{\mathrm{overload}}"
            r"- \lambda_b f_{\mathrm{balance}}"
            r"- \lambda_z f_{\mathrm{zone}}"
        )
        st.markdown(
            f"""
| 权重 | 取值 | 作用 |
|------|------|------|
| \(\\lambda_w\) (wait) | {lam.get('wait', 10)} | 提高高优先级患者上床收益 |
| \(\\lambda_o\) (overload) | {lam.get('overload', 1)} | 惩罚超负荷 |
| \(\\lambda_b\) (balance) | {lam.get('balance', 0.1)} | 促进分区负载均衡 |
| \(\\lambda_z\) (zone) | {lam.get('zone_mismatch', 0.5)} | 惩罚科室与床区不匹配 |
"""
        )
    with right:
        st.subheader("4.2 PPO（对照）")
        st.markdown(
            "采用 MaskablePPO：按患者顺序决策「选择某张床」或「继续等待」。"
            f"当前检查点按 **{ppo.get('inference_n_beds', 20)} 床** 训练，"
            "观测维度固定，与运行台侧栏的 CP-SAT 床位数相互独立。"
        )
        st.markdown("**裁剪代理目标**")
        st.latex(
            r"r_t(\theta)=\frac{\pi_\theta(a_t\mid s_t)}{\pi_{\theta_{\mathrm{old}}}(a_t\mid s_t)}"
        )
        st.latex(
            r"L^{\mathrm{CLIP}}(\theta)=\mathbb{E}_t\Big["
            r"\min\big(r_t(\theta)\hat{A}_t,\;"
            r"\mathrm{clip}(r_t(\theta),1-\epsilon,1+\epsilon)\hat{A}_t\big)\Big]"
        )
        st.markdown(
            f"其中 \(\\epsilon\) 对应 `clip_range` = {ppo.get('clip_range', 0.2)}。"
            "另含价值函数误差与策略熵项（Stable-Baselines3 默认组合）。"
        )

    st.header("5. 资源与模型文件")
    st.json(
        {
            "n_beds_cp_sat": res.get("n_beds"),
            "n_isolation_beds": res.get("n_isolation_beds"),
            "n_ventilators": res.get("n_ventilators"),
            "ppo_inference_n_beds": ppo.get("inference_n_beds", 20),
            "ppo_model": ppo.get("model_path"),
            "ppo_zip_present": (ROOT / "artifacts" / "ppo_icu.zip").exists(),
        }
    )
    disclaimer()
