from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict

from .config import results_dir
from .util import estimate_tokens, to_text


def _safe_part(text: str, n: int, head: bool) -> str:
    if n <= 0:
        return ""
    return text[:n] if head else text[-n:]


def store_original(tool_name: str, tool_call_id: str, text: str) -> Path:
    ts = time.strftime("%Y%m%d-%H%M%S")
    safe_tool = "".join(c if c.isalnum() or c in "-_" else "_" for c in (tool_name or "tool"))
    safe_call = "".join(c if c.isalnum() or c in "-_" else "_" for c in (tool_call_id or "call"))[:80]
    path = results_dir() / f"{ts}-{safe_tool}-{safe_call}.txt"
    path.write_text(text, encoding="utf-8", errors="replace")
    return path


def compress_result(
    *,
    tool_name: str,
    tool_call_id: str,
    result: Any,
    policy: Dict[str, Any],
    storage_enabled: bool = True,
) -> Dict[str, Any]:
    raw = to_text(result)
    mode = str(policy.get("mode") or "preview_store")
    if tool_name == "terminal" and mode == "terminal_evidence":
        from .terminal_evidence import terminal_result

        return terminal_result(
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            result=result,
            policy=policy,
            storage_enabled=storage_enabled,
        )
    if tool_name == "patch" and mode == "patch_diff_evidence":
        from .patch_diff_evidence import patch_result

        return patch_result(
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            result=result,
            policy=policy,
            storage_enabled=storage_enabled,
        )

    raw_chars = len(raw)
    min_chars = int(policy.get("min_chars") or 12000)
    head_chars = int(policy.get("preview_head_chars") or 3000)
    tail_chars = int(policy.get("preview_tail_chars") or 3000)

    if raw_chars < min_chars:
        return {
            "changed": False,
            "raw_text": raw,
            "compressed_text": raw,
            "raw_chars": raw_chars,
            "compressed_chars": raw_chars,
            "raw_tokens": estimate_tokens(raw),
            "compressed_tokens": estimate_tokens(raw),
            "stored_path": "",
        }

    stored_path = ""
    if storage_enabled:
        try:
            stored_path = str(store_original(tool_name, tool_call_id, raw))
        except Exception:
            stored_path = ""

    head = _safe_part(raw, head_chars, True)
    tail = _safe_part(raw, tail_chars, False)
    wrapper = {
        "tool_result_optimized": True,
        "tool_name": tool_name,
        "original_chars": raw_chars,
        "original_tokens_estimate": estimate_tokens(raw),
        "compression_mode": policy.get("mode") or "preview_store",
        "stored_path": stored_path,
        "preview": {
            "head": head,
            "tail": tail,
        },
        "note": "Original tool result was compressed before entering model context. Use read_file on stored_path if exact full output is needed.",
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
