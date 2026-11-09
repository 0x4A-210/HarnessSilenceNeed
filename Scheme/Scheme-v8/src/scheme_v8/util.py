from __future__ import annotations
import hashlib
import json
from dataclasses import asdict
from dataclasses import is_dataclass
from pathlib import Path
from typing import Any

def jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    return value

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(jsonable(value), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)

def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))

def inside(root: Path, relative: str) -> Path:
    p = Path(relative)
    if p.is_absolute() or '..' in p.parts or '\\' in relative:
        raise ValueError(f'Invalid relative path: {relative}')
    resolved = (root / p).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f'Path escapes input root: {relative}')
    return resolved


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _merge(base, override):
    result = dict(base)
    for key, value in override.items():
        result[key] = _merge(result[key], value) if isinstance(value, dict) and isinstance(result.get(key), dict) else value
    return result


ENGINES = ("obligation_ledger_dual", "cascade_session")
PROVIDERS = ("codex_cli", "claude_cli")


def load_config(path=None):
    """Load a pipeline config. `extends: <file>` overlays another config file
    (relative to this one). Relative workspace paths belong to this project."""
    import yaml
    path = Path(path) if path else PROJECT_ROOT / "configs/default.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Configuration must be a mapping")
    if "extends" in data:
        parent = path.parent / data.pop("extends")
        data = _merge(load_config(parent), data)
    llm = data.get("llm", {})
    expected = {"enabled": True, "obligation_policy": "split_coverage_compatibility",
                "function_reading": "whole", "unlimited_chars": True}
    for key, value in expected.items():
        if llm.get(key) != value:
            raise ValueError("Unsupported setting for current pipeline: llm." + key)
    if llm.get("engine") not in ENGINES:
        raise ValueError("llm.engine must be one of " + ", ".join(ENGINES))
    if llm.get("provider") not in PROVIDERS:
        raise ValueError("llm.provider must be one of " + ", ".join(PROVIDERS))
    if not llm.get("model") or data.get("analysis_scope") != "change_related":
        raise ValueError("Explicit model and change_related scope required")
    if any(k.endswith("base_run") or k.endswith("baseline") for k in llm):
        raise ValueError("External baseline dependencies are not supported")
    if llm.get("capacity_retries", 1) not in (0, 1, 2):
        raise ValueError("At most two transient retries per call")
    workspace = Path(data.get("workspace", "workspace"))
    data["workspace"] = str(workspace if workspace.is_absolute() else PROJECT_ROOT / workspace)
    return data
