"""Packaging boundaries, protocol stability and independently reproducible scoring."""
import ast
import importlib
import json
from pathlib import Path

import pytest
import yaml

from scheme_v8 import runner
from scheme_v8.evaluation.report import evaluate_run
from scheme_v8.llm.attribution.combine import combine
from scheme_v8.llm.attribution.pipeline import protocol_hashes
from scheme_v8.util import PROJECT_ROOT, digest, load_config, read_json, write_json


def test_protocol_matches_the_packaged_inference_protocol():
    expected = read_json(Path(__file__).with_name("expected_protocol.json"))
    assert protocol_hashes(load_config()) == expected


def test_all_project_imports_resolve_inside_this_package():
    root = PROJECT_ROOT / "src"
    for path in (root / "scheme_v8").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("scheme_"):
                assert node.module.startswith("scheme_v8.")
                imported = importlib.import_module(node.module)
                assert Path(imported.__file__).resolve().is_relative_to(root.resolve())


@pytest.mark.parametrize("setting,value", [("engine", "unsupported_engine"),
    ("obligation_policy", "unsupported_policy"), ("function_reading", "window"),
    ("unlimited_chars", False), ("refine_base_run", "outside")])
def test_config_does_not_enable_other_pipelines(tmp_path, setting, value):
    data = yaml.safe_load((PROJECT_ROOT / "configs/default.yaml").read_text())
    data["llm"][setting] = value
    path = tmp_path / "settings.yaml"
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError):
        load_config(path)


def test_local_batch_and_evaluation_need_no_labels_during_inference(make_input, tmp_path, monkeypatch):
    workspace = tmp_path / "standalone/workspace"
    workspace.mkdir(parents=True)
    labels, results = [], {}
    for label, origin, maintenance, temporal in [
        ("positive", True, "needs_update", "introduced"),
        ("positive", False, "needs_update", "unknown"),
        ("negative", None, "unknown", "unknown"),
    ]:
        fixture = make_input("int f(){return 1;}\n", "int f(){return 2;}\n")
        sid = read_json(fixture / "case.json")["id"]
        destination = workspace / "inputs" / sid
        destination.parent.mkdir(exist_ok=True)
        fixture.rename(destination)
        labels.append({"sample_id": sid, "original_id": sid, "project": "synthetic",
            "label_data": {"label": label, "degradation_type": "api", "need_visibility": "explicit",
                           "introduced_by_this_change": origin}})
        results[sid] = {"sample_id": sid, "maintenance_verdict": maintenance,
            "verdict": maintenance, "attribution_status": temporal,
            **combine({"verdict": maintenance}, {"status": temporal})}

    def mock_analysis(source, output, config):
        assert not (workspace / "private").exists()
        prediction = results[source.name]
        write_json(output / "prediction.json", prediction)
        (output / "report.md").write_text("synthetic report")
        return prediction

    monkeypatch.setattr(runner, "analyze", mock_analysis)
    config = load_config()
    config["workspace"] = str(workspace)
    run = workspace / "runs/current"
    assert runner.run_batch(workspace, run, config, progress=None)["samples"] == 3
    assert runner.verify_inputs(workspace)["samples"] == 3
    write_json(workspace / "private/ground_truth.json", labels)
    report = tmp_path / "standalone/reports/results.md"
    result = evaluate_run(workspace, run, report)
    assert result["metrics"]["maintenance"]["accuracy"] == 1
    assert result["metrics"]["temporal"]["accuracy"] == 0.5
    assert result["metrics"]["temporal"]["unresolved_preexisting"] == 1
    assert result["metrics"]["maintenance_resolution"]["strict_decision_accuracy"] == 2 / 3
    for label in labels:
        assert report.read_text().count("[" + label["original_id"] + "]") == 3
    with pytest.raises(FileExistsError):
        runner.run_batch(workspace, run, config, progress=None)
    (run / "predictions.json").write_text("[]")
    with pytest.raises(ValueError, match="Frozen artifact mismatch"):
        runner.verify_frozen(run)


def test_retry_rule_ignores_semantic_unknown_and_policy_refusal(tmp_path):
    def result(error):
        return {"whole_function_heads": {"maintenance": {"model_calls": [{"error": error}]}}}
    assert runner.retry_reason(result(None), tmp_path) is None
    assert runner.retry_reason(result("citation could not be grounded"), tmp_path) is None
    assert runner.retry_reason(result("Model timeout"), tmp_path)
    (tmp_path / "events.jsonl").write_text(json.dumps({"error": "content_policy_violation"}))
    assert runner.retry_reason(result("Model timeout"), tmp_path) is None
