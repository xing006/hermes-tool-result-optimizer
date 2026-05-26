from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List

from .compressor import store_original
from .util import estimate_tokens, safe_json_loads, to_text

ERROR_RE = re.compile(
    r"\b(error|failed|failure|exception|traceback|assertion|denied|timeout|timed out|not found|no such file|permission|refused|conflict|fatal|panic|segmentation fault)\b",
    re.IGNORECASE,
)
WARNING_RE = re.compile(r"\b(warn|warning|deprecated)\b", re.IGNORECASE)
FINAL_RE = re.compile(
    r"(=+ .* =+$|\b(short test summary|passed|failed|errors?|skipped|xfailed|xpassed|collected|success|finished|completed|done)\b)",
    re.IGNORECASE,
)
NOISE_RE = re.compile(
    r"(\r|\b\d{1,3}%\b|\[[#=>\.\s-]{10,}\]|\b(download|downloading|extracting|fetching)\b.*\b(\d+[%/]?|kb|mb|gb)\b)",
    re.IGNORECASE,
)


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _tail(text: str, n: int) -> str:
    return text[-n:] if n > 0 and len(text) > n else text


def _head(text: str, n: int) -> str:
    return text[:n] if n > 0 and len(text) > n else text


def _dedupe_keep_order(lines: Iterable[str], limit: int) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for line in lines:
        line = str(line).rstrip("\n")
        key = line.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(line)
        if len(out) >= limit:
            break
    return out


def _context_lines(lines: list[str], indexes: list[int], radius: int, limit: int) -> list[str]:
    selected: list[str] = []
    seen_idx: set[int] = set()
    for idx in indexes:
        start = max(0, idx - radius)
        end = min(len(lines), idx + radius + 1)
        for i in range(start, end):
            if i not in seen_idx:
                seen_idx.add(i)
                selected.append(lines[i])
                if len(selected) >= limit:
                    return selected
    return selected


def _extract_text_fields(raw: str) -> tuple[str, str, int | None, str]:
    """Best-effort parser for Hermes terminal results.

    Returns stdout, stderr, exit_code, and status. If the result is not structured,
    use the full text as stdout and status=unknown.
    """
    obj = safe_json_loads(raw)
    if isinstance(obj, dict):
        output = obj.get("output")
        stdout = obj.get("stdout")
        stderr = obj.get("stderr") or obj.get("error")
        exit_code = obj.get("exit_code")
        if stdout is None and output is not None:
            stdout = output
        try:
            exit_code_int = int(exit_code) if exit_code is not None else None
        except (TypeError, ValueError):
            exit_code_int = None
        status = "unknown"
        if exit_code_int is not None:
            status = "succeeded" if exit_code_int == 0 else "failed"
        return to_text(stdout or ""), to_text(stderr or ""), exit_code_int, status

    # Common textual fallback from tool wrappers.
    exit_match = re.search(r"[\"']?exit_code[\"']?\s*[:=]\s*(-?\d+)", raw)
    exit_code_int = None
    if exit_match:
        try:
            exit_code_int = int(exit_match.group(1))
        except ValueError:
            exit_code_int = None
    status = "unknown"
    if exit_code_int is not None:
        status = "succeeded" if exit_code_int == 0 else "failed"
    return raw, "", exit_code_int, status


def _meaningful_tail(text: str, limit_chars: int) -> str:
    if not text:
        return ""
    lines = text.splitlines()
    filtered = [line for line in lines if not NOISE_RE.search(line)]
    compact = "\n".join(filtered[-200:]) if filtered else text
    return _tail(compact, limit_chars)


def terminal_result(
    *,
    tool_name: str,
    tool_call_id: str,
    result: Any,
    policy: Dict[str, Any],
    storage_enabled: bool = True,
) -> Dict[str, Any]:
    raw = to_text(result)
    raw_chars = len(raw)
    stdout, stderr, exit_code, status = _extract_text_fields(raw)

    success_min = _as_int(policy.get("success_min_chars"), 40000)
    failure_min = _as_int(policy.get("failure_min_chars"), 80000)
    threshold = failure_min if status == "failed" else success_min
    if raw_chars < threshold:
        tokens = estimate_tokens(raw)
        return {
            "changed": False,
            "raw_text": raw,
            "compressed_text": raw,
            "raw_chars": raw_chars,
            "compressed_chars": raw_chars,
            "raw_tokens": tokens,
            "compressed_tokens": tokens,
            "stored_path": "",
        }

    stored_path = ""
    if storage_enabled:
        try:
            stored_path = str(store_original(tool_name, tool_call_id, raw))
        except Exception:
            stored_path = ""

    combined = (stdout + "\n" + stderr).strip() if stderr else stdout
    lines = combined.splitlines()
    error_indexes = [i for i, line in enumerate(lines) if ERROR_RE.search(line)]
    warning_lines = _dedupe_keep_order((line for line in lines if WARNING_RE.search(line)), _as_int(policy.get("max_warning_lines"), 40))
    final_lines = _dedupe_keep_order((line for line in lines[-300:] if FINAL_RE.search(line)), _as_int(policy.get("max_final_lines"), 30))
    error_lines = _context_lines(
        lines,
        error_indexes,
        _as_int(policy.get("error_context_lines"), 3),
        _as_int(policy.get("max_error_lines"), 80),
    )

    wrapper = {
        "tool_result_optimized": True,
        "tool_name": tool_name,
        "compression_mode": "terminal_evidence",
        "original_chars": raw_chars,
        "original_tokens_estimate": estimate_tokens(raw),
        "stored_path": stored_path,
        "evidence": {
            "status": status,
            "exit_code": exit_code,
            "stdout_head": _head(stdout, _as_int(policy.get("stdout_head_chars"), 1000)),
            "stdout_tail": _meaningful_tail(stdout, _as_int(policy.get("stdout_tail_chars"), 4000)),
            "stderr_tail": _meaningful_tail(stderr, _as_int(policy.get("stderr_tail_chars"), 8000)),
            "error_lines": error_lines,
            "warning_lines": warning_lines,
            "final_lines": final_lines,
        },
        "note": "Original terminal output was compressed before entering model context. Use read_file on stored_path if exact output is needed.",
    }
    compressed = json.dumps(wrapper, ensure_ascii=False)
    return {
        "changed": True,
        "raw_text": raw,
        "compressed_text": compressed,
        "raw_chars": raw_chars,
        "compressed_chars": len(compressed),
        "raw_tokens": estimate_tokens(raw),
        "compressed_tokens": estimate_tokens(compressed),
        "stored_path": stored_path,
    }
