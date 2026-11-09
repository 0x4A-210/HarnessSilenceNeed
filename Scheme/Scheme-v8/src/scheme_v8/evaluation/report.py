"""Current-only scores, six-dimension matrices and every sample's comparison."""
import os

from ..runner import verify_frozen
from ..util import digest, inside, read_json, write_json
from .dimensions import CELLS, TYPES
from .metrics import maintenance_resolution, three_matrices, three_metrics


def percent(value):
    return "N/A" if value is None else f"{value:.2%}"


def cell_name(row):
    return next(title for title, truth, visibility, origin in CELLS
                if row["truth"] == truth and row["need_visibility"] == visibility
                and (truth == "negative" or row["truth_introduced_by_this_change"] is origin))


def render_report(rows, metrics, matrices, run, destination):
    manifest = read_json(run / "run_manifest.json")
    archived = manifest.get("kind") == "packaged_current_run"
    lines = ["# 当前方案：Dataset-v7 评测结果", "",
        ("本报告由随包保存的本轮冻结预测重新计算；本次整理没有重新调用模型。"
         if archived else "本报告由本目录新运行并冻结的预测计算。"),
        f"共 {len(rows)} 条样本。模型、推理配置、证据和原始响应均保存在本目录。",
        "类型和显/隐、本次/非本次分组来自数据集真值，不代表检测器额外预测了这些类型。", "",
        "## 总体指标", "",
        "ACC 是准确率；P 是精确率。维护模块只有 needs_update 记为告警，unknown 记为未告警，"
        "因此阴性上的 unknown 可计入告警口径 TN，但不代表已经证明 satisfied_in_scope。", "",
        "时间指标仅评估具有时间真值的真实阳性，以 introduced（本次）为正类。真实本次的 unknown/no_gap 计 FN；"
        "真实非本次的 unknown/no_gap 不计 TN 或 FP，但仍计入 ACC 和误报率的分母。"
        "阴性没有本次/非本次真值，其伪缺口另列。综合严格口径要求阳性同时告警且归因正确，阴性不告警。", "",
        "| 判断 | ACC | P | 召回率 | 误报率 | 漏报率 | F1 | TP/FP/TN/FN |",
        "|---|---:|---:|---:|---:|---:|---:|---|"]
    for key, title in (("maintenance", "阳性/阴性"), ("temporal", "本次/非本次"), ("joint", "综合严格口径")):
        m = metrics[key]
        lines.append("| " + title + " | " + " | ".join(percent(m[x]) for x in
            ("accuracy", "precision", "recall", "false_positive_rate", "false_negative_rate", "f1"))
            + f" | {m['tp']}/{m['fp']}/{m['tn']}/{m['fn']} |")
    resolution = metrics["maintenance_resolution"]
    lines += ["", "## 未决与确认阴性", "", "| 真值 | needs_update | satisfied_in_scope | unknown |",
              "|---|---:|---:|---:|"]
    for truth, title in (("positive", "阳性"), ("negative", "阴性")):
        c = resolution["counts"][truth]
        lines.append(f"| {title} | {c['needs_update']} | {c['satisfied_in_scope']} | {c['unknown']} |")
    lines += ["", f"维护严格已证实判断准确率（unknown 均记错）：{percent(resolution['strict_decision_accuracy'])}。",
              f"时间模块：真实阳性中未决或 no_gap 共 {metrics['temporal']['unknown_or_no_gap']} 条，"
              f"已决但归因错误 {metrics['temporal']['wrong_decided']} 条；"
              f"真实阴性上报出缺口 {metrics['temporal']['false_gap_alarms_on_negatives']} 条。", ""]
    explanations = {
        "maintenance": "阳性格：检出/总数；阴性格：未告警/总数（可能含 unknown）。",
        "temporal": "阳性格：正确/错误/未决；阴性格：伪缺口/no_gap/unknown，不参与时间准确率。",
        "joint": "阳性格：告警且归因正确/总数；阴性格：未告警/总数。"}
    for section, title in (("maintenance", "维护判断"), ("temporal", "时间判断"), ("joint", "综合判断")):
        lines += [f"## {title}：类型 × 六维", "", explanations[section], "",
                  "| 类型 | " + " | ".join(c[0] for c in CELLS) + " |", "|---|" + "---:|" * 6]
        for kind in (*TYPES, "合计"):
            cells = []
            for name, truth, _, _ in CELLS:
                c = matrices[section][kind][name]
                if section == "maintenance":
                    value = f"{c['detected'] if truth == 'positive' else c['no_alarm']}/{c['total']}"
                elif section == "joint":
                    value = f"{c['exact'] if truth == 'positive' else c['no_alarm']}/{c['total']}"
                else:
                    keys = ("correct", "wrong", "unresolved") if truth == "positive" else ("gap_alarms", "no_gap", "unresolved")
                    value = "/".join(str(c[k]) for k in keys)
                cells.append(value)
            lines.append("| " + kind + " | " + " | ".join(cells) + " |")
        lines += [""]
    for section, title in (("maintenance", "维护判断逐条对照"), ("temporal", "时间判断逐条对照"), ("joint", "综合判断逐条对照")):
        lines += [f"## {title}", "", "| 样本 | 项目 | 类型 | 六维分组 | 真值 | 输出 | 对照 |",
                  "|---|---|---|---|---|---|---|"]
        for r in sorted(rows, key=lambda r: r["original_id"]):
            positive = r["truth"] == "positive"
            expected_time = "introduced" if r["truth_introduced_by_this_change"] else "preexisting"
            if section == "maintenance":
                truth = "阳性" if positive else "阴性"
                output = r["maintenance_verdict"]
                outcome = ("TP" if positive else "FP") if r["maintenance_alarm"] else ("FN" if positive else "TN（未告警）")
            elif section == "temporal":
                truth = expected_time if positive else "不适用"
                output = r["temporal_status"]
                outcome = ("正确" if output == truth else "错误" if output in ("introduced", "preexisting") else "未决/无缺口") if positive else ("伪缺口" if output in ("introduced", "preexisting") else "无时间真值")
            else:
                truth = "阳性/" + expected_time if positive else "阴性"
                output = "告警/" + r["joint_origin"] if r["joint_alarm"] else "未告警"
                correct = (r["joint_alarm"] and r["joint_origin"] == expected_time) if positive else not r["joint_alarm"]
                outcome = "正确" if correct else "综合漏判" if positive else "误报"
            relative = os.path.relpath(run / r["selected_path"] / "report.md", destination.parent)
            lines.append(f"| [{r['original_id']}]({relative}) | {r['project']} | {r['degradation_type']} | "
                         f"{cell_name(r)} | {truth} | {output} | {outcome} |")
        lines += [""]
    lines += ["## 结果边界", "", "这些结果来自同一开发数据集，不能作为独立测试集的泛化结论。"
              "本次整理保持推理提示词、判断逻辑与有效预算；未针对样本标签改变判断。"
              "代码使用语法解析和符号搜索补读证据，不包含完整控制流图、符号执行或编译级数据流证明。", ""]
    return "\n".join(lines)


def evaluate_run(workspace, run, report_path):
    verify_frozen(run)
    predictions = read_json(run / "predictions.json")
    dataset_manifest = workspace / "dataset_manifest.json"
    if dataset_manifest.exists():
        for name, checksum in read_json(dataset_manifest)["private_files"].items():
            if digest(inside(workspace, name).read_bytes()) != checksum:
                raise ValueError("Label metadata checksum mismatch: " + name)
    truth_list = read_json(workspace / "private/ground_truth.json")
    truth = {r["sample_id"]: r for r in truth_list}
    if len(truth) != len(truth_list) or len({p["sample_id"] for p in predictions}) != len(predictions):
        raise ValueError("Duplicate sample IDs")
    expected_inputs = read_json(run / "run_manifest.json")["inputs"]
    if set(expected_inputs) != {p["sample_id"] for p in predictions}:
        raise ValueError("Predictions do not cover the frozen input set exactly")
    selections = read_json(run / "selection.json")
    rows = []
    for p in predictions:
        sample = p["sample_id"]
        metadata = workspace / "inputs" / sample / "manifest.json"
        if digest(metadata.read_bytes()) != expected_inputs[sample]:
            raise ValueError("Input identity mismatch: " + sample)
        selected = selections[sample]["selected_path"]
        if read_json(inside(run, selected) / "prediction.json") != p:
            raise ValueError("Selected prediction differs from aggregate: " + sample)
        t = truth[sample]
        label = t["label_data"]
        rows.append({"sample_id": sample, "original_id": t["original_id"], "project": t["project"],
            "truth": label["label"], "degradation_type": label["degradation_type"],
            "need_visibility": label["need_visibility"],
            "truth_introduced_by_this_change": label.get("introduced_by_this_change"),
            "maintenance_verdict": p["maintenance_verdict"], "maintenance_alarm": p["maintenance_alarm"],
            "temporal_status": p["attribution_status"], "joint_alarm": p["joint_alarm"],
            "joint_origin": p["joint_origin"], "selected_path": selected})
    metrics = three_metrics(rows)
    metrics["maintenance_resolution"] = maintenance_resolution(rows)
    matrices = three_matrices(rows)
    for name, value in (("three_rows", rows), ("three_metrics", metrics), ("three_matrices", matrices)):
        write_json(run / "evaluation" / (name + ".json"), value)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(rows, metrics, matrices, run, report_path), encoding="utf-8")
    return {"samples": len(rows), "metrics": metrics, "report": str(report_path)}
