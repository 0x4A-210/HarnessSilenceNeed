#!/usr/bin/env python3
"""Reproduce the selected FSE 2026 harness-degradation ground truth.

This script intentionally keeps the paper's coverage-drop rule separate from
commit attribution. The rule is recomputed from archived OSS-Fuzz coverage;
the commit mapping is accepted only from the paper artifact's manually judged
case-study notes and the pinned configuration in config/positive_events.csv.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
RAW_COVERAGE_DIR = ROOT / "data" / "raw" / "coverage"
PROCESSED_DIR = ROOT / "data" / "processed"
EVIDENCE_DIR = ROOT / "evidence"
REPORTS_DIR = ROOT / "reports"
PROJECTS_DIR = ROOT / "sources" / "projects"
OSS_FUZZ_DIR = ROOT / "sources" / "oss-fuzz"

ANALYSIS_END = datetime(2024, 10, 1, tzinfo=timezone.utc)
# The released database is named 2024-10-30. This second bound prevents
# commits merged after data collection but carrying old author dates from
# leaking into a reproduction based on today's repository history.
SNAPSHOT_END = datetime(2024, 10, 30, 23, 59, 59, tzinfo=timezone.utc)
ARTIFACT_COMMIT = "73843108273b97f05a583bc5226fa8177d88eb04"
ARTIFACT_NOTES_URL = (
    "https://github.com/CISPA-SysSec/fuzz-harness-degradation/blob/"
    f"{ARTIFACT_COMMIT}/case_studies/notes.md"
)
GCS_REPORT = (
    "https://storage.googleapis.com/oss-fuzz-coverage/"
    "{project}/reports/{yyyymmdd}/linux/report.html"
)
WINDOW_DAYS = 30

TOTALS_RE = re.compile(
    r"<tfoot>.*?<pre>\s*Totals\s*</pre>.*?"
    r"<pre>\s*([0-9]+(?:\.[0-9]+)?)%\s*\((\d+)/(\d+)\)</pre>",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class Project:
    project: str
    repo_url: str
    oss_fuzz_intro_commit: str
    oss_fuzz_intro_time: datetime


@dataclass(frozen=True)
class Event:
    project: str
    event_date: date
    commit_id: str
    artifact_classification: str
    artifact_cause: str
    attribution_basis: str


@dataclass(frozen=True)
class Commit:
    commit_id: str
    parents: tuple[str, ...]
    author_time: datetime
    committer_time: datetime


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timezone is required: {value}")
    return parsed.astimezone(timezone.utc)


def iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def load_projects() -> list[Project]:
    with (CONFIG_DIR / "selected_projects.csv").open(newline="", encoding="utf-8") as handle:
        return [
            Project(
                project=row["project"],
                repo_url=row["repo_url"],
                oss_fuzz_intro_commit=row["oss_fuzz_intro_commit"],
                oss_fuzz_intro_time=parse_datetime(row["oss_fuzz_intro_time"]),
            )
            for row in csv.DictReader(handle)
        ]


def load_events() -> list[Event]:
    with (CONFIG_DIR / "positive_events.csv").open(newline="", encoding="utf-8") as handle:
        return [
            Event(
                project=row["project"],
                event_date=date.fromisoformat(row["event_date"]),
                commit_id=row["commit_id"],
                artifact_classification=row["artifact_classification"],
                artifact_cause=row["artifact_cause"],
                attribution_basis=row["attribution_basis"],
            )
            for row in csv.DictReader(handle)
        ]


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc.stdout


def git_commits(repo: Path) -> list[Commit]:
    raw = git(repo, "log", "--format=%x1e%H%x1f%P%x1f%aI%x1f%cI")
    commits: list[Commit] = []
    for record in raw.split("\x1e"):
        record = record.strip()
        if not record:
            continue
        fields = record.split("\x1f")
        if len(fields) != 4:
            raise RuntimeError(f"unexpected git record in {repo}: {record!r}")
        commit_id, parents, author_time, committer_time = fields
        commits.append(
            Commit(
                commit_id=commit_id,
                parents=tuple(parents.split()) if parents else (),
                author_time=parse_datetime(author_time),
                committer_time=parse_datetime(committer_time),
            )
        )
    return commits


def selected_commit_universe(project: Project) -> list[Commit]:
    commits = git_commits(PROJECTS_DIR / project.project)
    return [
        commit
        for commit in commits
        if project.oss_fuzz_intro_time <= commit.author_time <= ANALYSIS_END
        and commit.committer_time <= SNAPSHOT_END
    ]


def coverage_dates(events: Iterable[Event]) -> list[tuple[str, date]]:
    needed: set[tuple[str, date]] = set()
    for event in events:
        for offset in range(-WINDOW_DAYS, WINDOW_DAYS + 1):
            needed.add((event.project, event.event_date + timedelta(days=offset)))
    return sorted(needed)


def coverage_path(project: str, day: date) -> Path:
    return RAW_COVERAGE_DIR / project / day.strftime("%Y%m%d") / "report.html"


def download_one(project: str, day: date, retries: int = 3) -> dict[str, object]:
    output = coverage_path(project, day)
    url = GCS_REPORT.format(project=project, yyyymmdd=day.strftime("%Y%m%d"))
    if output.exists() and output.stat().st_size:
        payload = output.read_bytes()
        return {
            "project": project,
            "date": day.isoformat(),
            "url": url,
            "status": "cached",
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    last_error = ""
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "FSE2026-reproduction/1.0"})
            with opener.open(request, timeout=30) as response:
                payload = response.read()
            output.parent.mkdir(parents=True, exist_ok=True)
            temporary = output.with_suffix(".html.part")
            temporary.write_bytes(payload)
            temporary.replace(output)
            return {
                "project": project,
                "date": day.isoformat(),
                "url": url,
                "status": "downloaded",
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {
                    "project": project,
                    "date": day.isoformat(),
                    "url": url,
                    "status": "missing_404",
                    "bytes": 0,
                    "sha256": "",
                }
            last_error = f"HTTP {exc.code}: {exc.reason}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = repr(exc)
        time.sleep(2**attempt)
    return {
        "project": project,
        "date": day.isoformat(),
        "url": url,
        "status": f"error:{last_error}",
        "bytes": 0,
        "sha256": "",
    }


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def download_coverage(events: list[Event], workers: int) -> list[dict[str, object]]:
    pairs = coverage_dates(events)
    rows: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(download_one, project, day): (project, day)
            for project, day in pairs
        }
        for index, future in enumerate(as_completed(futures), 1):
            rows.append(future.result())
            if index % 100 == 0:
                print(f"coverage: {index}/{len(pairs)}", file=sys.stderr)
    rows.sort(key=lambda row: (str(row["project"]), str(row["date"])))
    write_csv(
        RAW_COVERAGE_DIR / "download_manifest.csv",
        ["project", "date", "url", "status", "bytes", "sha256"],
        rows,
    )
    errors = [row for row in rows if str(row["status"]).startswith("error:")]
    if errors:
        raise RuntimeError(f"{len(errors)} coverage downloads failed; see download_manifest.csv")
    return rows


def parse_coverage(project: str, day: date) -> dict[str, object] | None:
    path = coverage_path(project, day)
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8", errors="replace")
    match = TOTALS_RE.search(content)
    if not match:
        raise RuntimeError(f"could not parse total line coverage: {path}")
    displayed, covered, total = match.groups()
    covered_i, total_i = int(covered), int(total)
    calculated = covered_i / total_i * 100 if total_i else 0.0
    return {
        "date": day.isoformat(),
        "displayed_line_pct": float(displayed),
        "line_covered": covered_i,
        "line_total": total_i,
        "line_pct": calculated,
        "path": str(path.relative_to(ROOT)),
        "url": GCS_REPORT.format(project=project, yyyymmdd=day.strftime("%Y%m%d")),
    }


def center(values: list[float]) -> float:
    return (statistics.mean(values) + statistics.median(values)) / 2


def event_metrics(event: Event) -> dict[str, object]:
    reports: dict[date, dict[str, object]] = {}
    for offset in range(-WINDOW_DAYS, WINDOW_DAYS + 1):
        day = event.event_date + timedelta(days=offset)
        parsed = parse_coverage(event.project, day)
        if parsed is not None:
            reports[day] = parsed

    before_reports = [
        reports[day]
        for day in sorted(reports)
        if event.event_date - timedelta(days=WINDOW_DAYS) <= day < event.event_date
    ]
    after_reports = [
        reports[day]
        for day in sorted(reports)
        if event.event_date <= day <= event.event_date + timedelta(days=WINDOW_DAYS)
    ]
    if not before_reports or not after_reports or event.event_date not in reports:
        raise RuntimeError(f"insufficient coverage reports for {event.project}-{event.event_date}")

    before_values = [float(report["line_pct"]) for report in before_reports]
    after_values = [float(report["line_pct"]) for report in after_reports]
    previous_report = before_reports[-1]
    event_report = reports[event.event_date]
    before_center = center(before_values)
    after_center = center(after_values)
    day_swing = float(event_report["line_pct"]) - float(previous_report["line_pct"])
    long_swing = after_center - before_center
    max_swing = max(after_values) - max(before_values)
    predicates = {
        "event_line_pct_above_zero": float(event_report["line_pct"]) > 0,
        "single_day_drop_below_minus_5pp": day_swing < -5,
        "long_window_drop_below_minus_5pp": long_swing < -5,
        "max_window_drop_below_minus_5pp": max_swing < -5,
    }
    return {
        "metric_name": "artifact_30d_center_line_coverage_pct",
        "metric_before": before_center,
        "metric_after": after_center,
        "before_mean": statistics.mean(before_values),
        "after_mean": statistics.mean(after_values),
        "before_median": statistics.median(before_values),
        "after_median": statistics.median(after_values),
        "before_max": max(before_values),
        "after_max": max(after_values),
        "previous_observed_date": previous_report["date"],
        "previous_observed_pct": previous_report["line_pct"],
        "event_observed_pct": event_report["line_pct"],
        "single_day_swing_pp": day_swing,
        "long_window_swing_pp": long_swing,
        "max_window_swing_pp": max_swing,
        "before_valid_reports": len(before_reports),
        "after_valid_reports": len(after_reports),
        "predicates": predicates,
        "automated_filter_reproduced": all(predicates.values()),
        "before_reports": before_reports,
        "after_reports": after_reports,
    }


def commit_lookup(project: Project) -> tuple[list[Commit], dict[str, Commit]]:
    all_commits = git_commits(PROJECTS_DIR / project.project)
    return all_commits, {commit.commit_id: commit for commit in all_commits}


def commit_web_url(repo_url: str, commit_id: str) -> str:
    return f"{repo_url.removesuffix('.git')}/commit/{commit_id}"


def artifact_event_url(event: Event) -> str:
    anchor = f"{event.project}-{event.event_date.isoformat()}"
    return f"{ARTIFACT_NOTES_URL}#{anchor}"


def build_outputs(projects: list[Project], events: list[Event]) -> dict[str, object]:
    project_by_name = {project.project: project for project in projects}
    if set(event.project for event in events) - set(project_by_name):
        raise RuntimeError("positive event references a project outside selected_projects.csv")

    project_commits: dict[str, list[Commit]] = {}
    project_lookup: dict[str, dict[str, Commit]] = {}
    universes: dict[str, list[Commit]] = {}
    for project in projects:
        all_commits, lookup = commit_lookup(project)
        project_commits[project.project] = all_commits
        project_lookup[project.project] = lookup
        universes[project.project] = [
            commit
            for commit in all_commits
            if project.oss_fuzz_intro_time <= commit.author_time <= ANALYSIS_END
            and commit.committer_time <= SNAPSHOT_END
        ]

    event_rows: list[dict[str, object]] = []
    detailed_events: list[dict[str, object]] = []
    metric_rows: list[dict[str, object]] = []
    positive_by_hash: dict[tuple[str, str], dict[str, object]] = {}

    for event in events:
        project = project_by_name[event.project]
        commit = project_lookup[event.project].get(event.commit_id)
        if commit is None:
            raise RuntimeError(f"commit does not exist: {event.project} {event.commit_id}")
        universe_hashes = {item.commit_id for item in universes[event.project]}
        if event.commit_id not in universe_hashes:
            raise RuntimeError(f"event commit is outside paper window: {event.project} {event.commit_id}")
        ancestor = subprocess.run(
            [
                "git", "-C", str(PROJECTS_DIR / event.project),
                "merge-base", "--is-ancestor", event.commit_id, "HEAD",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
        if not ancestor:
            raise RuntimeError(f"event commit is not on default-branch ancestry: {event.project} {event.commit_id}")
        metrics = event_metrics(event)
        previous_commit = commit.parents[0] if commit.parents else ""
        harness_id = f"{event.project}::project_aggregate"
        sources = [
            artifact_event_url(event),
            metrics["before_reports"][-1]["url"],
            metrics["after_reports"][0]["url"],
            commit_web_url(project.repo_url, event.commit_id),
        ]
        output_row = {
            "project": event.project,
            "commit_id": event.commit_id,
            "commit_time": iso_z(commit.author_time),
            "harness_id": harness_id,
            "previous_commit": previous_commit,
            "degradation_label": "positive",
            "degradation_metric_before": f"{float(metrics['metric_before']):.6f}",
            "degradation_metric_after": f"{float(metrics['metric_after']):.6f}",
            "evidence_source": " | ".join(str(source) for source in sources),
        }
        event_rows.append(output_row)
        positive_by_hash[(event.project, event.commit_id)] = output_row
        metric_rows.append(
            {
                "project": event.project,
                "event_date": event.event_date.isoformat(),
                "commit_id": event.commit_id,
                "artifact_classification": event.artifact_classification,
                "artifact_cause": event.artifact_cause,
                **{key: value for key, value in metrics.items() if key not in {"before_reports", "after_reports", "predicates"}},
                **{f"predicate_{key}": value for key, value in metrics["predicates"].items()},
            }
        )
        detailed_events.append(
            {
                "project": event.project,
                "event_date": event.event_date.isoformat(),
                "commit_id": event.commit_id,
                "commit_time": iso_z(commit.author_time),
                "committer_time": iso_z(commit.committer_time),
                "previous_commit": previous_commit,
                "all_parents": list(commit.parents),
                "default_branch_ancestor": ancestor,
                "coverage_after_commit_calendar_check": event.event_date >= commit.author_time.date(),
                "harness_id": harness_id,
                "harness_scope": "all fuzz targets in the project's aggregate OSS-Fuzz coverage report",
                "artifact_classification": event.artifact_classification,
                "artifact_cause": event.artifact_cause,
                "attribution_basis": event.attribution_basis,
                "artifact_evidence": artifact_event_url(event),
                "commit_evidence": commit_web_url(project.repo_url, event.commit_id),
                "metrics": metrics,
            }
        )

    event_rows.sort(key=lambda row: (str(row["project"]), str(row["commit_time"])))
    write_csv(
        PROCESSED_DIR / "degradation_events.csv",
        [
            "project", "commit_id", "commit_time", "harness_id", "previous_commit",
            "degradation_label", "degradation_metric_before", "degradation_metric_after",
            "evidence_source",
        ],
        event_rows,
    )

    metric_fieldnames = [
        "project", "event_date", "commit_id", "artifact_classification", "artifact_cause",
        "metric_name", "metric_before", "metric_after", "before_mean", "after_mean",
        "before_median", "after_median", "before_max", "after_max",
        "previous_observed_date", "previous_observed_pct", "event_observed_pct",
        "single_day_swing_pp", "long_window_swing_pp", "max_window_swing_pp",
        "before_valid_reports", "after_valid_reports", "automated_filter_reproduced",
        "predicate_event_line_pct_above_zero",
        "predicate_single_day_drop_below_minus_5pp",
        "predicate_long_window_drop_below_minus_5pp",
        "predicate_max_window_drop_below_minus_5pp",
    ]
    write_csv(PROCESSED_DIR / "coverage_event_metrics.csv", metric_fieldnames, metric_rows)

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / "positive_event_evidence.json").write_text(
        json.dumps(detailed_events, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    universe_rows: list[dict[str, object]] = []
    for project in projects:
        for commit in universes[project.project]:
            positive = positive_by_hash.get((project.project, commit.commit_id))
            universe_rows.append(
                positive
                if positive is not None
                else {
                    "project": project.project,
                    "commit_id": commit.commit_id,
                    "commit_time": iso_z(commit.author_time),
                    "harness_id": f"{project.project}::project_aggregate",
                    "previous_commit": commit.parents[0] if commit.parents else "",
                    # These rows are deliberately not called negative: the paper
                    # released coverage-drop cases, not exhaustive commit labels.
                    "degradation_label": "unlabeled",
                    "degradation_metric_before": "",
                    "degradation_metric_after": "",
                    "evidence_source": commit_web_url(project.repo_url, commit.commit_id),
                }
            )
    universe_rows.sort(key=lambda row: (str(row["project"]), str(row["commit_time"]), str(row["commit_id"])))
    write_csv(
        PROCESSED_DIR / "commit_universe.csv",
        [
            "project", "commit_id", "commit_time", "harness_id", "previous_commit",
            "degradation_label", "degradation_metric_before", "degradation_metric_after",
            "evidence_source",
        ],
        universe_rows,
    )

    per_project = {
        project.project: {
            "commit_total": len(universes[project.project]),
            "positive_degradation_commits": sum(
                1 for event in events if event.project == project.project
            ),
            "oss_fuzz_intro_time": iso_z(project.oss_fuzz_intro_time),
            "repo_head": git(PROJECTS_DIR / project.project, "rev-parse", "HEAD").strip(),
        }
        for project in projects
    }
    positives = len({(event.project, event.commit_id) for event in events})
    reproduced = sum(bool(row["automated_filter_reproduced"]) for row in metric_rows)
    summary: dict[str, object] = {
        "project_count": len(projects),
        "commit_total": sum(len(universes[project.project]) for project in projects),
        "positive_degradation_commits": positives,
        "positive_events_reproducing_all_automatic_predicates": reproduced,
        "positive_events_from_artifact_manual_or_exploratory_set": positives - reproduced,
        "go_no_go": "NO-GO: fewer than 30 positive commit mappings",
        "analysis_start_per_project": "first OSS-Fuzz harness/integration commit",
        "analysis_end": iso_z(ANALYSIS_END),
        "repository_snapshot_guard": iso_z(SNAPSHOT_END),
        "nonpositive_commit_label": "unlabeled (not asserted negative)",
        "per_project": per_project,
    }
    (ROOT / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return summary


def write_validation(summary: dict[str, object], events: list[Event]) -> None:
    evidence = json.loads((EVIDENCE_DIR / "positive_event_evidence.json").read_text(encoding="utf-8"))
    artifact_notes = (ROOT / "artifact" / "case_studies" / "notes.md").read_text(
        encoding="utf-8"
    )
    checks: list[tuple[str, bool]] = []
    for item in evidence:
        prefix = f"{item['project']} {item['commit_id']}"
        artifact_heading = f"#### {item['project']}-{item['event_date']}"
        heading_start = artifact_notes.find(artifact_heading)
        artifact_section = ""
        if heading_start >= 0:
            section_tail = artifact_notes[heading_start + len(artifact_heading):]
            next_headings = [
                position
                for position in (
                    section_tail.find("\n#### "),
                    section_tail.find("\n### "),
                )
                if position >= 0
            ]
            section_end = min(next_headings) if next_headings else len(section_tail)
            artifact_section = section_tail[:section_end]
        predicates = item["metrics"]["predicates"]
        checks.extend(
            [
                (f"{prefix}: default-branch commit exists", bool(item["default_branch_ancestor"])),
                (f"{prefix}: parent commit recorded", bool(item["previous_commit"])),
                (f"{prefix}: coverage day is not before commit day", bool(item["coverage_after_commit_calendar_check"])),
                (f"{prefix}: before/after reports available", bool(item["metrics"]["before_reports"]) and bool(item["metrics"]["after_reports"])),
                (f"{prefix}: artifact case-study entry exists", heading_start >= 0),
                (f"{prefix}: artifact event section names commit", item["commit_id"] in artifact_section),
                (f"{prefix}: artifact event section records cause", f"cause: {item['artifact_cause']}" in artifact_section),
                (f"{prefix}: all automatic degradation predicates hold", all(predicates.values())),
                (f"{prefix}: before metric exceeds after metric", float(item["metrics"]["metric_before"]) > float(item["metrics"]["metric_after"])),
                (f"{prefix}: project-aggregate harness scope is explicit", item["harness_id"] == f"{item['project']}::project_aggregate"),
            ]
        )
    failed = [name for name, passed in checks if not passed]
    lines = [
        "# Validation report",
        "",
        f"Validated all {len(events)} positive mappings (the requested 10–20-case audit sample).",
        "",
        f"- Projects: {summary['project_count']}",
        f"- Commits in universe: {summary['commit_total']}",
        f"- Positive degradation commits: {summary['positive_degradation_commits']}",
        f"- Checks executed: {len(checks)}",
        f"- Failed checks: {len(failed)}",
        "",
        "Each positive was checked for commit existence on current default-branch ancestry, exact UTC author time, first parent, temporal ordering at calendar-day resolution, archived coverage availability, an artifact event section that names the exact commit and cause, all original automatic coverage-drop predicates, before/after metric ordering, and explicit project-aggregate harness scope. Exact build time within an OSS-Fuzz report day is not published; attribution therefore comes from the artifact's two-judge case-study notes rather than an inferred intra-day ordering.",
        "",
    ]
    if failed:
        lines.extend(["## Failures", "", *[f"- {name}" for name in failed], ""])
    else:
        lines.extend(["All checks passed.", ""])
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "validation.md").write_text("\n".join(lines), encoding="utf-8")
    if failed:
        raise RuntimeError(f"validation failed: {failed}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["download", "build", "all"])
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()

    projects = load_projects()
    events = load_events()
    if not 5 <= len(projects) <= 10:
        raise RuntimeError("the requested subset must contain 5–10 projects")
    if args.command in {"download", "all"}:
        download_coverage(events, args.workers)
    if args.command in {"build", "all"}:
        summary = build_outputs(projects, events)
        write_validation(summary, events)
        print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
