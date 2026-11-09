import argparse
import json
from pathlib import Path

from .engine import analyze
from .runner import run_batch, verify_frozen, verify_inputs
from .util import PROJECT_ROOT, inside, load_config


def main():
    parser = argparse.ArgumentParser(description="Current standalone dual-module harness checker")
    parser.add_argument("--config", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("analyze", help="Run both independent heads on one prepared input")
    one.add_argument("--input", type=Path, required=True)
    one.add_argument("--output", type=Path, required=True)
    batch = sub.add_parser("batch", help="Fresh inference over all local prepared inputs")
    batch.add_argument("--run", required=True, help="New run directory name")
    evaluate = sub.add_parser("evaluate", help="Score frozen predictions; no model calls")
    evaluate.add_argument("--run", default="current")
    verify = sub.add_parser("verify", help="Verify all input and selected-run artifact checksums")
    verify.add_argument("--run", default="current")
    args = parser.parse_args()
    config = load_config(args.config)
    workspace = Path(config["workspace"])
    if args.command == "analyze":
        prediction = analyze(args.input.resolve(), args.output.resolve(), config)
        result = {k: prediction[k] for k in ("sample_id", "maintenance_verdict", "attribution_status", "joint_alarm", "joint_origin")}
    else:
        run = inside(workspace / "runs", args.run)
        if args.command == "batch":
            result = run_batch(workspace, run, config)
        elif args.command == "verify":
            result = {"inputs": verify_inputs(workspace), "frozen_files": verify_frozen(run)}
        else:
            from .evaluation.report import evaluate_run
            report_path = PROJECT_ROOT / "reports" / ("测试结果.md" if args.run == "current" else args.run + ".md")
            result = evaluate_run(workspace, run, report_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
