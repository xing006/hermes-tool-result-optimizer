from __future__ import annotations

import logging
from typing import Any

from .compressor import compress_result
from .config import load_settings, tool_policy
from .telemetry import record_compressed, record_raw

logger = logging.getLogger(__name__)


def post_tool_call(**kwargs: Any) -> None:
    settings = load_settings()
    if not settings.get("enabled", True) or not (settings.get("telemetry", {}) or {}).get("enabled", True):
        return None
    try:
        record_raw(
            tool_name=kwargs.get("tool_name") or "",
            args=kwargs.get("args") or {},
            result=kwargs.get("result") or "",
            task_id=kwargs.get("task_id") or "",
            session_id=kwargs.get("session_id") or "",
            tool_call_id=kwargs.get("tool_call_id") or "",
            duration_ms=int(kwargs.get("duration_ms") or 0),
        )
    except TypeError:
        # Older local function signature guard if edited during development.
        record_raw(
            tool_name=kwargs.get("tool_name") or "",
            result=kwargs.get("result") or "",
            task_id=kwargs.get("task_id") or "",
            session_id=kwargs.get("session_id") or "",
            tool_call_id=kwargs.get("tool_call_id") or "",
            duration_ms=int(kwargs.get("duration_ms") or 0),
        )
    except Exception as exc:
        logger.debug("tool-result-optimizer post_tool_call failed: %s", exc)
    return None


def transform_tool_result(**kwargs: Any) -> str | None:
    settings = load_settings()
    if not settings.get("enabled", True) or not (settings.get("compression", {}) or {}).get("enabled", True):
        return None
    tool_name = kwargs.get("tool_name") or ""
    tool_call_id = kwargs.get("tool_call_id") or ""
    result = kwargs.get("result") or ""
    try:
        policy = tool_policy(tool_name, settings)
        out = compress_result(
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            result=result,
            policy=policy,
            storage_enabled=bool((settings.get("storage", {}) or {}).get("enabled", True)),
        )
        record_compressed(
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            raw_chars=int(out["raw_chars"]),
            raw_tokens=int(out["raw_tokens"]),
            compressed_chars=int(out["compressed_chars"]),
            compressed_tokens=int(out["compressed_tokens"]),
            changed=bool(out["changed"]),
            stored_path=out.get("stored_path") or "",
            compressed_text=out.get("compressed_text") or "",
        )
        if out["changed"]:
            return out["compressed_text"]
    except Exception as exc:
        logger.debug("tool-result-optimizer transform_tool_result failed: %s", exc)
    return None
