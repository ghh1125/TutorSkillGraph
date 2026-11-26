"""Render the verified observations and proposed revision from the same case object."""


def markdown(case: dict) -> str:
    observed = case["observed"]
    assessment = observed["independent_assessment"]
    plan = case["proposed"]
    edit = plan["edit"]
    fraction = float(assessment["raw_fraction"])
    maximum = assessment["max_points"]
    log = observed["log"]
    lines = [
        "# p019 围栏课应该怎样收尾",
        "",
        f"**当前判断为{plan['current_decision']}。** 单门题改对后，值得检验学生是否能自行处理多个开口。公开数据支持重建原课和设计诊断题，对 p019 的补教建议仍缺一份独立作答及理由。",
        "",
        "## 实际记录",
        "",
        "练习给出 500 英尺围栏和一个 10 英尺宽的门洞，要求用矩形边长 x、y 写出围栏长度约束。下表按发言顺序列出中文转述与可检索的英文片段。",
        "",
        "| 话轮 | 说话者 | 记录内容 | 原文片段 |",
        "| --- | --- | --- | --- |",
    ]
    for t in observed["turns"]:
        speaker = "学生" if t["role"] == "user" else "导师"
        lines.append(f"| {t['turn']} | {speaker} | {t['paraphrase']} | `{t['excerpt']}` |")
    lines.extend([
        "",
        f"定位键为 `p019 / gate_fence`，CSV 逻辑记录 {log['record']}（表头计为 1），物理行 {log['first_line']}–{log['last_line']}。[固定版原始对话]({log['link']})",
        "",
        f"{assessment['related_public_item']} 该生三道练习对应变式题合计为 {fraction * maximum:.0f}/{maximum} 分（{fraction:.1%}）。{assessment['missing_reason']} [后测题面]({assessment['paper']}) · [逐人结果]({assessment['score_source']['link']}) · [字段字典]({assessment['codebook']})",
        "",
        "## 我们提出的判断",
        "",
        plan["purpose"], "", plan["relationship_to_observation"], "",
        plan["interpretations"]["all_openings"], "", plan["interpretations"]["one_opening_only"], "",
        "以下方程是根据两种解释推导的预测。第一行另有第 7 轮真实算式可核对，后两行的学生回答均未知。",
        "",
        "| 题目 | 开口宽度（英尺） | A 会写什么 | B 会写什么 |",
        "| --- | --- | --- | --- |",
    ])
    for p in plan["predictions"]:
        widths = "、".join(map(str, p["gate_widths_ft"]))
        alternatives = " 或 ".join(f"`{eq}`" for eq in p["one_opening_only"])
        lines.append(f"| {p['task']} | {widths} | `{p['all_openings']}` | {alternatives} |")
    lines.extend([
        "",
        "Farm Gates 中两个门宽不同，解释 B 允许只取其中任一个。等宽双门题把门宽保持在原来的 10 英尺，只改变门数。",
        "",
        "### 新设计的诊断题",
        "", "> " + plan["probe_prompt"], "", plan["interpret_probe"], "",
        "### 拟修改的一个步骤", "",
        edit["location"] + " " + edit["v0"], "", edit["v1"], "",
        "### 哪些结果会改变判断", "",
    ])
    for criterion in ("withdraw", "try", "clarify", "pending"):
        lines.append("- " + plan["individual_criteria"][criterion])
    lines.extend([
        "", "### 怎样检验下一批学生是否受益", "", edit["control"], "",
        edit["transfer"], "", edit["cohort_withdrawal"], "",
    ])
    return "\n".join(lines)
