from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

@dataclass
class InputCase:
    sample_id: str
    root: Path
    project: str
    target: str
    harness_files: list[str]
    build_script: str | None
    manifest: dict

@dataclass
class ChangeGroup:
    id: str
    path: str
    old_path: str
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    added_lines: list[int]
    removed: list[str]
    added: list[str]
    heading: str = ''
    status: str = 'unresolved'
    reason: str = ''

@dataclass
class EvidenceRef:
    id: str
    path: str
    start: int
    end: int
    content_hash: str
    reason: str
    version: str = 'M'
