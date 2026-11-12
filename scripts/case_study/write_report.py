"""Build the Chinese presentation report from verified case results."""
from __future__ import annotations
import json
from pathlib import Path


def table(headers, rows):
    def cell(value):
        return str(value).replace("|", "／").replace("\n", "<br>")
    return "\n".join(["| " + " | ".join(map(cell, headers)) + " |",
        "| " + " | ".join("---" for _ in headers) + " |"] +
        ["| " + " | ".join(map(cell, row)) + " |" for row in rows]) + "\n"


def names(values):
    items = sorted(values)
    return "、".join(items) if items else "无"


def dest(solution, pid, zones):
    if pid in solution["assignment"]:
        b = solution["assignment"][pid]
        return f"B{b:02}({zones[str(b)]})"
    return "普通病房" if pid in solution["ward"] else "等待"


def short_unit(unit):
    return {"Medical Intensive Care Unit (MICU)": "MICU",
        "Medical/Surgical Intensive Care Unit (MICU/SICU)": "MICU/SICU",
        "Surgical Intensive Care Unit (SICU)": "SICU",
        "Trauma SICU (TSICU)": "TSICU",
        "Cardiac Vascular Intensive Care Unit (CVICU)": "CVICU",
        "Coronary Care Unit (CCU)": "CCU",
        "Neuro Intermediate": "Neuro Intermediate（神经中间监护）"}.get(unit, unit)


def write_report(data, out):
    history_path = Path(data["input_sources"]["history"])
    hist = json.loads(history_path.read_text(encoding="utf-8"))
    observed = {r["stay_id"]: r for r in hist["patients"]}
    patients, static = data["patients"], data["static"]
    zones = {str(k): v for k, v in data["bed_zones"].items()}
    rows = {r["pid"]: r for r in static["rows"]}
    evidence = {(r["pid"], r["hour"]): r for r in data["evidence"]}
    front = sorted(static["front"], key=lambda r: r["name"])
    selected = static["selected"]
    # select() and the front share a representative decision, but JSON serializes
    # them separately. Find its displayed name by objective vector.
    selected_name = next(r["name"] for r in front if r["f"] == selected["f"])
    lines = []
    def add(text=""):
        lines.append(text)

    add("# ICU 床位调度案例：12 名患者的 Pareto 方案与两小时滚动展示\n")
    add("整理日期：2026 年 11 月 12 日。模型口径依据所附《多目标多约束的 ICU 床位调度算法》理论报告。\n")
    add("## 1. 汇报时先讲这几个结果\n")
    add("本案例使用 **12 名 MIMIC-IV 真实患者的临床快照**，设置 **6 张 ICU 床和 2 个普通病房名额**，得到 **6 个互不支配的 Pareto 目标向量**。所有静态方案都占用 6 张 ICU 床、使用 2 个病房名额，区别在于收治谁、谁等待、是否跨病区，以及是否把模型定义的重症患者安排到普通病房。\n")
    add("- **S1：病区全部匹配，重症入病房为 0，优先级服务量 12,850 分。**\n"
        "- **S3：重症入病房仍为 0，允许 2 人跨病区，服务量增至 13,300 分。**\n"
        "- **S6：同样 2 人跨病区，允许 1 名重症患者进入普通病房，服务量进一步增至 13,400 分。**\n")
    add(f"本次演示按预先固定的“先减少重症入病房、再最大化服务量、再减少病区失配”规则选择 **{selected_name}**。它是这项偏好下的执行方案；S1 等其他方案对应不同偏好。\n")
    add("滚动部分使用同一组 12 名患者，每 2 小时重算，展示 **T+4h、T+8h、T+12h** 三次出床后更换收治名单，以及 T+2h、T+6h 新患者先进入等待队列的过程。\n")
    add("**真实对照的范围：**已从本地 MIMIC 原始压缩包提取这 12 人的 **80 条原始位置事件记录**，可展示实际入住病区、出入科时间和后续去向。原始表没有具体床号、同一时刻全部空床和完整候诊队列，因此本文将其称为“历史实际诊疗去向”，不能据此声称模型优于医生实际排床。公平的数值比较另使用明确标注的规则基线。\n")

    add("## 2. 数据来源与研究设定\n")
    add(table(["内容", "本案例取法", "性质"], [
        ["患者标识、临床观测", "MIMIC-IV 本地 50 例样本中选取 12 例；临床 h24～36 共 84 个快照", "真实记录"],
        ["性别、近似年龄", "原始 patients 表；近似年龄按 anchor_age + 入 ICU 年份 − anchor_year", "真实字段计算；不是精确生日年龄"],
        ["实际入科、转科、出科", "原始 icustays 和 transfers 表，共 12 条 stay、80 条位置事件记录", "真实记录；仅用于事后对照"],
        ["候选患者同时出现", "把不同真实日期的病例组合成一个有限候选池", "模拟并发；不是医院同一天的真实队列"],
        ["6 张 ICU 床、2 个普通病房名额", "按第 3 节设定", "研究场景；不是 MIMIC 公开的真实容量"],
        ["到达与床位释放", "按第 7 节明确列出的事件表推进", "人工设定的模拟事件"],
        ["病情随时间变化", "每步只使用对应时点已记录的真实临床快照", "真实观测；不预测未来病情"],
    ]))
    add("选样目的为便于讲清楚多目标取舍，优先保留多个病区、不同分数、并在 h24～36 三项分量齐备的病例。这是事后完整病例演示，不是随机代表性样本或前瞻验证。h0 普遍尚无已记录的评分证据，因此不把 h0 的缺失贡献零当作患者正常。\n")
    add("### 2.1 评分与优先级\n")
    add("附件采用 0～12 分指标，而现有样本的原始 `sofa_total` 是六分量 0～24 分。为匹配附件，本例重新计算：\n\n"
        "`s = 凝血分量 + 肝分量 + 肾分量`，每项 0～4 分，合计 0～12 分。\n")
    add("以下均称“三分量评分”，不把它写成临床完整 SOFA。肾分量沿用样本已计算的肾评分；该评分流程允许尿量参与，但逐条核对本组 84 个快照后，肾分均等于肌酐单独阈值分，因此本组与三项化验口径数值一致。选定的 84 个快照三项分量均非缺失，未用零填补缺失。\n")
    add("优先级按附件公式计算：`w = 1 + 0.6 × s/12 + 0.4 × L分位数`，`W = floor(1000 × w)`。本例所有患者在每个比较时点采用相同的已观察临床时长（静态为各自入 ICU 后 24h），经验分布中并列值取 `P(L≤当前L)=1`，故静态 **w = 1.4 + 0.05s**。此例中的时长项是常数，不能用来证明等待时间或复合优先级的独立效果。未使用最终住院时长、真实未来出科时间计算优先级。\n")
    add("隔离需求和当前呼吸机需求未取得可直接使用的独立真实标签，患者表均记为“未知”，两项约束关闭；未根据病区名称或单个分数臆造标签。\n")

    add("## 3. 床位与资源参数\n")
    add(table(["床位号", "模拟病区", "是否为隔离床", "初始状态"], [
        [f"B{int(b):02}", {"MICU":"内科 MICU", "SICU":"外科 SICU", "CCU":"心脏监护 CCU", "NICU":"神经监护 NICU"}[z], "否", "空床"]
        for b, z in zones.items()]))
    add(table(["参数", "取值", "解释"], [
        ["ICU 总床数 m", 6, "MICU 1、SICU 2、CCU 2、NICU 1"],
        ["隔离床数", 0, "隔离标签未知，C3 不启用"],
        ["呼吸机容量", "未设定", "需求未知，C4 不启用；不据此评价设备可行性"],
        ["普通病房总容量 W", 2, "容量池，不编造具体普通病房床号"],
        ["初始已有病房占用 ω", 0, "滚动中随转入人数累积，之后不重置"],
        ["研究重症阈值 θ", 5, "s≥5 计入本模型重症标记"],
        ["研究病房资格上限 η", 6, "s≤6 具备本模型病房资格"],
        ["每步新增重症入病房上限 K", 1, "允许 ε2 为 0 或 1，显示取舍"],
        ["每步 ICU 挪床上限 M", 2, "只统计仍在 ICU 的旧患者换床"],
        ["对外转出上限 R", 0, "不启用转出床池变量；模拟出院为外生事件"],
        ["在院患者保留", "开启", "旧患者必须留 ICU 或合法转病房，不能被重新扔回等待队列"],
        ["ICU 占用下限 L0", 6, "rho=1；本案例每一步均保持满床"],
        ["滚动步长", "2 小时", "T=0,2,4,6,8,10,12，共 7 个时点"],
    ]))
    add("θ、η、K 是演示附件数学权衡的研究参数，不是实际转普通病房的临床标准。本例的病房资格完全按附件简化评分判断，未增加诊断、治疗支持或医生转科许可条件。真实病区映射为 MICU→MICU、SICU/TSICU→SICU、CCU/CVICU→CCU、Neuro Intermediate→NICU；最后一项是研究层的神经监护归并，不表示 Neuro Intermediate 在原始资料中就是 ICU。\n")

    add("## 4. 12 名患者的具体情况\n")
    patient_rows = []
    clinical_rows = []
    for pid, p in patients.items():
        actual = observed[p["stay_id"]]
        sex = {"M":"男", "F":"女"}[actual["patient_demographics"]["gender"]]
        e = evidence[pid, 24]
        c = e["components"]
        patient_rows.append([pid, p["stay_id"], f"{sex}／约{actual['approx_age_at_icu_year']}岁",
            short_unit(p["first_careunit"]), p["preferred_zone"],
            "/".join(str(c[k]) for k in ("coagulation","liver","renal")), rows[pid]["score"],
            f"{float(rows[pid]['weight']):.2f}", rows[pid]["W"],
            "是" if rows[pid]["score"] >= 5 else "否", "是" if rows[pid]["score"] <= 6 else "否"])
        clinical_rows.append([pid, e["inputs"].get("platelet", "未记录"),
            e["inputs"].get("bilirubin", "未记录"), e["inputs"].get("creatinine", "未记录"),
            "/".join(str(c[k]) for k in ("coagulation","liver","renal")), "未知", "未知"])
    add(table(["编号", "stay_id", "性别／近似年龄", "记录中的首入病区", "模型首选病区", "凝血/肝/肾分", "三分量总分 s", "权重 w", "整数 W", "模型重症", "病房资格"], patient_rows))
    add("静态比较时 12 人均视为待分配候选，无上一轮 ICU 床号；年龄和性别仅作患者描述，不进入权重或分配条件。诊断未在本例补充提取，不由病区名称推断疾病。\n")
    add("### 4.1 h24 的主要化验观测\n")
    add(table(["编号", "血小板 K/μL", "总胆红素 mg/dL", "肌酐 mg/dL", "凝血/肝/肾分", "隔离需求", "呼吸机需求"], clinical_rows))
    add("化验值取源快照 `inputs` 的对应评分窗口观测，不是同一抽血时刻的整套检验；完整证据保留观测时间、入库时间、项目编码。本组肾分已与肌酐阈值逐条核对。\n")

    add("## 5. 静态 Pareto 结果：每条方案到底安排了谁\n")
    add("比较的活动轴为 **f1 优先级服务量越高越好、f2 重症入普通病房人数越少越好、f4 病区失配人数越少越好**。f0 是 ICU 占床数，f3 是病区负载极差，f5 是挪床次数。f1 同时计入 ICU 与本次进入普通病房的人，等待患者不计入。\n")
    add(table(["方案", "ICU占床 f0", "服务量 f1 ↑", "重症入病房 f2 ↓", "负载极差 f3", "病区失配 f4 ↓", "挪床 f5", "病房占用", "等待人数"],
              [[r["name"], *r["f"], len(r["ward"]), len(r["waiting"])] for r in front]))
    add("f1 的单位是整数优先级分，13,300 分即权重和 13.30。此处负载为 MICU 1、SICU 2、CCU 2、NICU 1，满床时 f3 固定为 1，不能宣称某个方案改善了病区均衡。静态没有在院上一轮床位，故 f5 全为 0。\n")
    add("### 5.1 床位清单\n")
    placement = []
    for b, z in zones.items():
        placement.append([f"B{int(b):02} ({z})"] + [next((p for p, bed in r["assignment"].items() if bed == int(b)), "空") for r in front])
    placement.append(["普通病房（2名）"] + [names(r["ward"]) for r in front])
    placement.append(["等待（4名）"] + [names(r["waiting"]) for r in front])
    placement.append(["跨病区患者"] + [names(p for p, b in r["assignment"].items() if patients[p]["preferred_zone"] != zones[str(b)]) for r in front])
    placement.append(["重症入普通病房者"] + [names(p for p in r["ward"] if rows[p]["score"] >= 5) for r in front])
    add(table(["位置／去向"] + [r["name"] for r in front], placement))
    add("每列是一条完整且可行的方案。相同目标向量下可能有其他床位排列，表中仅选一个代表；不能把同一目标向量的床号互换计成新的 Pareto 点。\n")
    add("### 5.2 怎样解释方案的取舍\n")
    add("1. **S1→S3：服务量增加 450 分，重症入病房仍为 0，但增加 2 人跨病区。**S1 的神经病区收治 P11，S3 改由高分的 P03 跨入神经监护，并增加 P02 的跨区收治。服务人次仍为 8，提升的是所服务患者的优先级总量。\n"
        "2. **S3→S6：服务量增加 100 分，跨病区人数仍为 2，但重症入病房从 0 变为 1。**S3 病房为 P07、P09，S6 改为 P04、P09，即以模型重症患者 P04（s=5）替代 P07（s=3）。这是研究参数允许的权衡，不能据此直接建议临床转科。\n"
        "3. **S1 与 S4：病区失配同为 0。**S4 多获得 250 分服务量，同时将 P03（s=6）放入普通病房，故两者也不能互相支配。\n")
    add("上述六点都不存在另一个方案同时满足“f1 不低、f2 不高、f4 不高”且至少一项严格更好。因此，选择一条执行方案仍需要明确偏好。\n")
    add(f"本次静态选择 **{selected_name}**：先令 f2 最小，再最大化 f1，再最小化 f4；并列时减少挪床。它允许 2 人跨病区，不把模型重症患者送入普通病房。若汇报对象要求跨病区为零，可展示 S1。\n")

    add("## 6. 与 MIMIC 历史实际去向及规则基线比较\n")
    add("### 6.1 MIMIC 里能够看到什么\n")
    add("已实际检查本地 `mimic-iv-3.1.zip`，并流式读取全部 2,413,581 条 transfers、94,458 条 icustays 和 364,627 条 patients，分别保留本组病例。核对 12 个样本 stay 的入出科字段均与原始 icustays 一致。80 条位置事件中，transfer 48 条、admit 12 条、discharge 12 条、ED 8 条，不能称为 80 次转科。\n")
    add(table(["原始表", "与调度相关的字段", "可以还原", "缺少"], [
        ["icu/icustays", "stay_id, first_careunit, last_careunit, intime, outtime", "一次 ICU stay 的类型和时间", "具体床号、床位容量"],
        ["hosp/transfers", "transfer_id, eventtype, careunit, intime, outtime", "患者逐次实际科室去向", "完整候诊池、分床规则、空床及设备台账"],
    ]))
    add("`transfer_id` 标识一条患者位置事件，不是可跨患者复用的床位编号；同一病区多条 transfer 记录也不能自动解释为真实换床。以上字段含义与 [MIMIC transfers 官方说明](https://mimic.mit.edu/docs/iv/modules/hosp/transfers.html) 和 [icustays 官方说明](https://mimic.mit.edu/docs/iv/modules/icu/icustays.html) 一致。\n")
    add("### 6.2 同组患者：真实诊疗去向与模拟方案并列\n")
    compare = []
    for pid, p in patients.items():
        o = observed[p["stay_id"]]
        actual = "、".join(short_unit(u) for u in o["actual_careunit_at_clinical_hour"]["24"])
        compare.append([pid, actual] + [dest(r, pid, zones) for r in front if r["name"] in ("S1", "S3", "S6")])
    add(table(["患者", "历史实际 h24 病区", "模拟 S1", "模拟 S3（本次选择）", "模拟 S6"], compare))
    add("真实 h24～36 内这 12 人均维持相应监护病区，未发生本案例设定的三次离床事件。真实病例分属不同日期，表中的“实际”列不构成同一时点的 12 人排床结果；不得把它强行放进模拟 6 床、2 病房条件，计算“医生方案不可行”或“模型节省床位”。Neuro Intermediate 保留原始类别，不改写成真实 ICU。\n")
    add("### 6.3 真实入出科时间与转科轨迹\n")
    actual_times = []
    for pid, p in patients.items():
        raw = observed[p["stay_id"]]["raw_icustay"]
        actual_times.append([pid, raw["intime"], raw["outtime"]])
    add(table(["患者", "真实 ICU stay 入科时间", "真实 ICU stay 出科时间"], actual_times))
    add("时间保持 MIMIC 原始去标识化时间格式，仅用于回顾定位。不同患者的这些日期不构成真实并发场景。\n")
    add("以下均为原始 transfers 的回顾性记录，小时数相对于该患者真实 ICU 入科时刻；仅展示病区变化，合并同病区连续记录。\n")
    actual_tracks = []
    for pid in ("P02", "P05", "P08", "P10"):
        p = patients[pid]
        tracks = []
        last = None
        for tr in observed[p["stay_id"]]["transfers"]:
            h = tr["relative_intime_hours"]
            if h is None or h < 0 or tr["eventtype"].lower() == "discharge":
                continue
            if tr["careunit"] == last:
                continue
            tracks.append(f"h{h:.2f} {short_unit(tr['careunit'])}")
            last = tr["careunit"]
            if len(tracks) >= 3:
                break
        actual_tracks.append([pid, " → ".join(tracks)])
    add(table(["患者", "真实病区轨迹片段"], actual_tracks))
    add("P02 的原始 transfers 在早期记录为 SICU，h21.76 后转 MICU；icustays 的首入病区字段为 MICU。两种原始字段保留各自含义，本例 h24 比较采用 transfers 当时所在病区。后续真实转科时间不进入求解器，不能视为当前可用的出院预测。\n")
    add("### 6.4 同候选池、同资源下的规则基线\n")
    add("基线规则事先写明：按模拟队列编号 P01→P12 依次收 ICU，优先选空闲首选病区，否则选最小空床号；满床后按同一顺序把合格患者安排到病房，并遵守 K=1。队列顺序是演示输入，不是 MIMIC 真实候诊顺序；此基线也不是医生的实际策略。\n")
    base = static["baseline"]
    add(table(["方案", "ICU人数", "病房人数", "服务量 f1 ↑", "重症入病房 f2 ↓", "病区失配 f4 ↓", "等待人数"],
        [["规则基线", base["f"][0], len(base["ward"]), base["f"][1], base["f"][2], base["f"][4], len(base["waiting"])]] +
        [[r["name"],r["f"][0],len(r["ward"]),r["f"][1],r["f"][2],r["f"][4],len(r["waiting"])] for r in front if r["name"] in ("S1","S3","S6")]))
    add(f"规则基线 ICU：{names(base['assignment'])}；病房：{names(base['ward'])}；等待：{names(base['waiting'])}。\n")
    add("S6 相比规则基线：f1 从 13,350 增至 13,400，f2 同为 1，f4 从 5 降至 2，在本场景活动轴上支配该基线。S3 相比基线少 50 分服务量，同时把 f2 从 1 降为 0、f4 从 5 降为 2；这体现偏好取舍，不能写成所有指标都更优。结果仅支持本例规则对照，不外推为优于临床医生。\n")

    add("## 7. 两小时滚动调度展示\n")
    add("### 7.1 同一组患者，模拟时钟怎样推进\n")
    add("T=0 对应每名患者各自的临床 h24，T+2h 对应各自 h26，依此类推。模拟时钟不是患者之间共享的真实日历时间。所有临床评分按当时可记录的信息更新；到达、离床事件由模拟器在对应时点提供，求解器不提前看到未来事件。\n")
    add(table(["模拟时点", "新到达候选池（模拟）", "出院／离开 ICU 床池（模拟）", "对应真实评分时点"],
        [[f"T+{r['hour']}h", names(r["arrivals"]), names(r["discharges"]), f"各自入 ICU 后 h{r['score_hour']}"] for r in data["rolling"]["history"]]))
    add("T=0 仅有 10 人可见，P02、P06 尚未到达候选池。每轮都重新扫描当前前沿并应用同一选解规则，保留已入住患者。普通病房占用跨步累计；本次仿真不设普通病房出院事件，名额用满后不再释放。\n")
    add("### 7.2 每一步完整床位表\n")
    roll_rows = []
    for h in data["rolling"]["history"]:
        s = h["executed"]
        cells = [next((p for p,b in s["assignment"].items() if b == int(bed)), "空") for bed in zones]
        roll_rows.append([f"T+{h['hour']}h", *cells, names(h["ward_total"]), names(h["waiting"]),
                         names(h["pending"]), names(h["discharged_total"])])
    add(table(["时点"]+[f"B{int(b):02} {z}" for b,z in zones.items()]+["病房累计", "等待", "尚未到达", "已离床累计"], roll_rows))
    add("### 7.3 重点讲述的调度变化\n")
    changes = []
    for h in data["rolling"]["history"]:
        hour = h["hour"]
        if hour == 0:
            changes.append(["T+0h", "首轮调度", "10 人中 6 人进入 ICU，P09、P11 进入病房，P10、P12 等待；P02、P06 尚未进入候选池。"])
        elif hour == 2:
            changes.append(["T+2h", "高分患者到达但无空床", "P02（s=7）到达。ICU 和病房均满，且保留约束禁止把原在院患者重新放回队列，因此 P02 等待。高优先级不意味着可以无限抢占。"])
        elif hour == 4:
            changes.append(["T+4h", "释放 B01 后新收治", "模拟 P01 离床，P02 从等待进入 B01(MICU)；其余 5 名 ICU 患者原床不动。"])
        elif hour == 6:
            changes.append(["T+6h", "新到达先进入队列", "P06（s=5）到达，当前无空床，排入等待；病房已有 P09、P11，不因重算而重新出现 2 个名额。"])
        elif hour == 8:
            changes.append(["T+8h", "释放外科床后收治", "模拟 P05 离床，P06 从等待进入 B02(SICU)；既有 ICU 患者不换床。"])
        elif hour == 10:
            changes.append(["T+10h", "评分变化但排床保持", "P08 三分量分数从 5 升至 6，优先级整数权重从 1,650 升至 1,700；其仍在 B05。评分变化不必然引起调床。"])
        elif hour == 12:
            changes.append(["T+12h", "释放心脏监护床后补位", "模拟 P08 离床，P10（s=1）从等待进入 B05(CCU)；P12 继续等待。P08 的临床 h36 评分虽可用于回顾展示，但它已先离床，不参与本步求解。"])
    add(table(["时点", "触发原因", "执行变化与解释"], changes))
    add("三次新入 ICU 均填补刚释放的床位，**挪床数 f5 每步均为 0**；新入床、出院、转病房不算挪床。本例已体现队列、出床和病情更新下的再决策，但不能用它证明有挪床操作、滚动策略比静态策略更优，或挪床上限已产生约束效果。\n")
    add("### 7.4 真实评分序列与每步指标\n")
    add(table(["患者", "h24", "h26", "h28", "h30", "h32", "h34", "h36", "说明"],
        [[pid]+[evidence[pid,h]["sofa12"] for h in range(24,38,2)]+[note]
        for pid,note in [("P08","先保持5，h34为6，h36为4；全段三分量完整"),
                          ("P09","4→3→4；全段三分量完整；入病房后不再作为优化候选")]]))
    add("P09 的病情序列仅作回顾展示：按附件普通病房容量池的边界，转病房后不再进入候选集，也不触发再入 ICU。不能把这一行解释成模型持续管理普通病房患者。\n")
    metric_rows = []
    for h in data["rolling"]["history"]:
        f = h["executed"]["f"]
        metric_rows.append([f"T+{h['hour']}h",len(h["rows"]), f[0],len(h["old_ward"]),
            len(h["executed"]["ward"]),len(h["ward_total"]), f[1],f[2],f[4],f[5],len(h["front"]),"通过"])
    add(table(["时点", "本步候选数", "ICU数", "步前病房占用", "新增入病房", "病房累计", "本步 f1", "新增重症入病房 f2", "病区失配 f4", "挪床 f5", "前沿点数", "12人守恒"], metric_rows))
    add("**指标口径：**本步 f1 只包含当前候选集中分到 ICU 或本次新入病房的人；以前已转病房者不再计入。本例 T+0h 的 13,100 分与 T+2h 的 9,950 分分母不同，不表示患者服务质量骤降。每轮均验证“ICU + 等待 + 待到达 + 已离床 + 病房 = 12”，五类两两不交；对外转出集合始终为空。\n")

    add("## 8. 计算、核查和可复现性\n")
    add("本次在交付目录使用独立 CP-SAT 演示实现附件模型，不修改原仓库。原因是现有仓库的 `f2` 仍是部分 ICU 床上的 SOFA 分数和，且未实现普通病房变量；直接给现有输出换标签会与附件公式不一致。\n")
    control = static["independent_validation"]
    add(table(["核查项", "结果"], [
        ["活动轴及方向", "仅比较 (f1最大化, f2最小化, f4最小化)"],
        ["ε 网格", "ε2∈{0,1}，ε4∈{0,1,2,3,4,5,6}，每个时点 14 个整数单元"],
        ["并列处理", "依次证明最优 f1、f2、f4，随后减少 f5 并选代表床位"],
        ["最优状态", "所有已接受单元的各级求解均为 OPTIMAL；不可行单元保留 INFEASIBLE"],
        ["静态完整性", f"对本例全部整数 ε 范围扫描，得到 6 个互不支配目标向量；另独立枚举 {control['feasible_patient_partitions']:,} 个 ICU/病房患者组合，前沿完全一致"],
        ["指标复算", "逐方案从患者名单和床位独立重算六项目标"],
        ["硬约束", "逐方案核查一人一去向、一床一人、6床下限、病房容量/资格/重症上限、旧患者保留、挪床上限"],
        ["时间和状态", "先处理当步事件，再求解；旧记录不被后续离床改写；病房容量累计；每步患者守恒"],
        ["评分证据", "使用对应时点快照，核查观测/记录时间不晚于快照末端；最终 LOS 和后续转科仅用于事后对照"],
        ["求解器", f"OR-Tools {data['software']['ortools']}；单线程；随机种子 0；每级限时 10 秒"],
    ]))
    add("完整性结论只适用于本例有限候选池、给定约束和三个活动轴。没有临床疗效、死亡率或真实等待时间的对照实验，也未做全样本统计推广。\n")
    add("### 8.1 复跑\n")
    add("在项目根目录执行，路径替换为本地输入位置：\n\n```powershell\n"
        "python scripts/case_study/build_case.py --input artifacts/sofa_sample/sofa_sample.json "
        "--history reports/icu_case_20261112/mimic_history.json --output reports/icu_case_20261112\n```\n")
    add("患者输入与位置事件不随仓库分发；理论附件可通过 `--theory` 指定并记录哈希。只重新生成文字报告可加 `--report-only`。结果保存在不入 Git 的 reports 目录，不写数据库，不覆盖现有项目模型。\n")
    add("### 8.2 配套文件\n")
    add(table(["文件", "用途"], [
        ["ICU调度案例汇报.md", "本报告，含完整输入、6个方案、实际去向、滚动变化"],
        ["case_results.json", "所有评分证据、静态/滚动单元、患者去向、求解状态与核查结果"],
        ["mimic_history.json", "12例原始入出科、80条位置事件、人口学与源文件CRC"],
        ["build_case.py / write_report.py", "可复跑计算和报告生成脚本"],
    ]))
    add("## 9. 可直接照着讲的口述稿\n")
    add("我们从 MIMIC 选了十二名有真实临床记录的患者，把他们放入六张 ICU 床和两个普通病房名额的模拟场景。这里列出了每人的评分、病区和去向。六个 Pareto 方案都可行，但侧重点不同。S1 完全匹配病区，服务量是 12,850 分；S3 保持重症入病房为零，增加两人跨病区，服务量达到 13,300 分；S6 再允许一名模型重症患者进入普通病房，达到 13,400 分。因此模型给出的不是唯一答案，我们还要明确偏好，本次选择 S3。\n")
    add("MIMIC 里确实有真实入出科和转科记录，所以我们也把这些患者的实际去向放在旁边。但它没有床号、当时空床和完整排队名单，不能说已经还原了医生排床。最后看滚动表：每两小时重新决策，新到达患者先等待，第四、第八、第十二小时床位释放后分别接收等待患者。整个过程始终满床，旧患者没有被退回队列，也没有发生挪床。\n")

    target = out / "ICU调度案例汇报.md"
    target.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report: {target} ({target.stat().st_size:,} bytes)")
