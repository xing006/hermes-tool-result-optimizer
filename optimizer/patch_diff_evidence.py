from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

from .compressor import store_original
from .util import estimate_tokens, to_text

FILE_RE = re.compile(r"^(diff --git a/(.+?) b/(.+)|\*\*\* Update File: (.+)|---\s+(?:a/)?(.+)|\+\+\+\s+(?:b/)?(.+))")
HUNK_RE = re.compile(r"^@@\s+[-+0-9, ]+@@")
FAIL_RE = re.compile(r"\b(fail|failed|error|exception|traceback|could not|not found|no such file|syntaxerror|invalid|reject|conflict)\b", re.IGNORECASE)
SYNTAX_RE = re.compile(r"\b(syntax|lint|check|py_compile|eslint|tsc|mypy|ruff|pytest)\b", re.IGNORECASE)
RISK_RE = re.compile(
    r"(delete|remove|drop|rm|unlink|auth|token|password|secret|key|config|provider|model|tool|subprocess|shell|eval|exec|permission|admin|path|import|database|migration|schema|sys\.path)",
    re.IGNORECASE,
)


@dataclass
class Hunk:
    header: str
    lines: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join([self.header] + self.lines)

    @property
    def risk_markers(self) -> list[str]:
        found: list[str] = []
        for m in RISK_RE.finditer(self.text):
            marker = m.group(0).lower()
            if marker not in found:
                found.append(marker)
        return found


@dataclass
class DiffFile:
    path: str
    header_lines: list[str] = field(default_factory=list)
    hunks: list[Hunk] = field(default_factory=list)

    @property
    def risk_markers(self) -> list[str]:
        found: list[str] = []
        for h in self.hunks:
            for marker in h.risk_markers:
                if marker not in found:
                    found.append(marker)
        return found


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _is_failure(raw: str) -> bool:
    # Patch failures must stay uncompressed so exact diagnostics are visible.
    return bool(FAIL_RE.search(raw)) and not ("diff --git" in raw or "@@" in raw or "*** Update File:" in raw)


def _pick_path(match: re.Match[str]) -> str:
    for i in range(2, 7):
        try:
            value = match.group(i)
        except IndexError:
            value = None
        if value and value != "/dev/null":
            return value.strip()
    return "unknown"


def parse_diff(raw: str) -> list[DiffFile]:
    files: list[DiffFile] = []
    current: DiffFile | None = None
    current_hunk: Hunk | None = None

    for line in raw.splitlines():
        fm = FILE_RE.match(line)
        is_new_file = False
        if fm:
            path = _pick_path(fm)
            if current is None or (line.startswith("diff --git") or line.startswith("*** Update File:")):
                current = DiffFile(path=path)
                files.append(current)
                current_hunk = None
                is_new_file = True
            elif current and (line.startswith("+++") or line.startswith("---")):
                # Keep ---/+++ headers on the current file, but prefer +++ path as display path.
                if line.startswith("+++") and path != "unknown":
                    current.path = path

        if current is None:
            continue

        if HUNK_RE.match(line):
            current_hunk = Hunk(header=line)
            current.hunks.append(current_hunk)
            continue

        if current_hunk is not None:
            current_hunk.lines.append(line)
        else:
            current.header_lines.append(line)

    return files


def _count_changes(files: list[DiffFile]) -> tuple[int, int]:
    insertions = 0
    deletions = 0
    for f in files:
        for h in f.hunks:
            for line in h.lines:
                if line.startswith("+++") or line.startswith("---"):
                    continue
                if line.startswith("+"):
                    insertions += 1
                elif line.startswith("-"):
                    deletions += 1
    return insertions, deletions


def _syntax_status(raw: str) -> str:
    lines = [line.strip() for line in raw.splitlines() if SYNTAX_RE.search(line)]
    if not lines:
        return "unknown"
    joined = "\n".join(lines[-8:])
    if FAIL_RE.search(joined):
        return "failed"
    return "passed"


def _select_hunks(hunks: list[Hunk], first_n: int, last_n: int, max_hunks: int) -> list[Hunk]:
    selected: list[Hunk] = []

    def add(h: Hunk) -> None:
        if h not in selected and len(selected) < max_hunks:
            selected.append(h)

    for h in hunks[:first_n]:
        add(h)
    for h in hunks:
        if h.risk_markers:
            add(h)
    for h in hunks[-last_n:] if last_n > 0 else []:
        add(h)
    if not selected and hunks:
        add(hunks[0])
    return selected


def patch_result(
    *,
    tool_name: str,
    tool_call_id: str,
    result: Any,
    policy: Dict[str, Any],
    storage_enabled: bool = True,
) -> Dict[str, Any]:
    raw = to_text(result)
    raw_chars = len(raw)
    min_chars = _as_int(policy.get("success_min_chars") or policy.get("min_chars"), 40000)
    raw_tokens = estimate_tokens(raw)

    if raw_chars < min_chars or _is_failure(raw):
        return {
            "changed": False,
            "raw_text": raw,
            "compressed_text": raw,
            "raw_chars": raw_chars,
            "compressed_chars": raw_chars,
            "raw_tokens": raw_tokens,
            "compressed_tokens": raw_tokens,
            "stored_path": "",
        }

    files = parse_diff(raw)
    if not files:
        return {
            "changed": False,
            "raw_text": raw,
            "compressed_text": raw,
            "raw_chars": raw_chars,
            "compressed_chars": raw_chars,
            "raw_tokens": raw_tokens,
            "compressed_tokens": raw_tokens,
            "stored_path": "",
        }

    stored_path = ""
    if storage_enabled:
        try:
            stored_path = str(store_original(tool_name, tool_call_id, raw))
        except Exception:
            stored_path = ""

    first_hunks = _as_int(policy.get("first_hunks_per_file"), 2)
    last_hunks = _as_int(policy.get("last_hunks_per_file"), 1)
    max_hunks_per_file = _as_int(policy.get("max_hunks_per_file"), 8)
    max_hunk_chars = _as_int(policy.get("max_hunk_chars"), 12000)

    file_previews: list[dict[str, Any]] = []
    hunks_total = 0
    hunks_shown = 0
    for f in files:
        selected = _select_hunks(f.hunks, first_hunks, last_hunks, max_hunks_per_file)
        hunks_total += len(f.hunks)
        hunks_shown += len(selected)
        preview_parts: list[str] = []
        hunk_truncated = False
        for h in selected:
            text = h.text
            if len(text) > max_hunk_chars:
                text = text[:max_hunk_chars] + "\n... [hunk truncated]"
                hunk_truncated = True
            preview_parts.append(text)
        file_previews.append({
            "path": f.path,
            "hunks_total": len(f.hunks),
            "hunks_shown": len(selected),
            "hunks_omitted": max(0, len(f.hunks) - len(selected)),
            "risk_markers": f.risk_markers,
            "hunk_truncated": hunk_truncated,
            "preview": "\n".join(preview_parts),
        })

    insertions, deletions = _count_changes(files)
    wrapper = {
        "tool_result_optimized": True,
        "tool_name": tool_name,
        "compression_mode": "patch_diff_evidence",
        "original_chars": raw_chars,
        "original_tokens_estimate": raw_tokens,
        "stored_path": stored_path,
        "summary": {
            "files_changed": len(files),
            "hunks_total": hunks_total,
            "hunks_shown": hunks_shown,
            "hunks_omitted": max(0, hunks_total - hunks_shown),
            "insertions": insertions,
            "deletions": deletions,
            "syntax_check": _syntax_status(raw),
        },
        "files": file_previews,
        "note": "Original patch output was compressed before entering model context. Use read_file on stored_path for complete diff.",
    }
    compressed = json.dumps(wrapper, ensure_ascii=False)
    return {
        "changed": True,
        "raw_text": raw,
        "compressed_text": compressed,
        "raw_chars": raw_chars,
        "compressed_chars": len(compressed),
        "raw_tokens": raw_tokens,
        "compressed_tokens": estimate_tokens(compressed),
        "stored_path": stored_path,
    }
