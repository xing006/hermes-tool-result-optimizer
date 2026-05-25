from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

DEFAULTS: Dict[str, Any] = {
    "enabled": True,
    "telemetry": {"enabled": True},
    "compression": {
        "enabled": True,
        "min_chars": 12000,
        "mode": "preview_store",
        "preview_head_chars": 3000,
        "preview_tail_chars": 3000,
    },
    "storage": {"enabled": True, "retention_days": 14},
    "tools": {
        # Long command output is usually useful at the end. Keep a small header for command/context,
        # preserve more tail for errors, summaries, and final test output.
        "terminal": {"min_chars": 8000, "mode": "preview_store", "preview_head_chars": 1000, "preview_tail_chars": 7000},
        # Extracted pages often have useful title/intro and references/footer. Keep balanced preview.
        "web_extract": {"min_chars": 12000, "mode": "preview_store", "preview_head_chars": 4000, "preview_tail_chars": 4000},
        # Full skill docs can be very large; keep concise bookends and store original.
        "skill_view": {"min_chars": 8000, "mode": "preview_store", "preview_head_chars": 2500, "preview_tail_chars": 2500},
        # Browser snapshots are structure-heavy; keep enough top nav plus bottom state.
        "browser_snapshot": {"min_chars": 10000, "mode": "preview_store", "preview_head_chars": 3000, "preview_tail_chars": 3000},
        "browser_navigate": {"min_chars": 10000, "mode": "preview_store", "preview_head_chars": 3000, "preview_tail_chars": 3000},
        # Diffs/code review data should remain deterministic, not LLM summarized.
        "patch": {"min_chars": 16000, "mode": "preview_store", "preview_head_chars": 5000, "preview_tail_chars": 5000},
        "default": {"min_chars": 12000, "mode": "preview_store", "preview_head_chars": 3000, "preview_tail_chars": 3000},
    },
}


def hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home
        return Path(get_hermes_home())
    except Exception:
        return Path(os.path.expanduser("~")) / "AppData" / "Local" / "hermes"


def state_dir() -> Path:
    p = hermes_home() / "tool-result-optimizer"
    p.mkdir(parents=True, exist_ok=True)
    return p


def results_dir() -> Path:
    p = state_dir() / "results"
    p.mkdir(parents=True, exist_ok=True)
    return p


def telemetry_db_path() -> Path:
    return state_dir() / "telemetry.sqlite"


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_settings() -> Dict[str, Any]:
    cfg: Dict[str, Any] = {}
    try:
        from hermes_cli.config import load_config
        root = load_config() or {}
        cfg = root.get("tool_result_optimizer") or {}
    except Exception:
        cfg = {}
    return _deep_merge(DEFAULTS, cfg if isinstance(cfg, dict) else {})


def tool_policy(tool_name: str, settings: Dict[str, Any] | None = None) -> Dict[str, Any]:
    settings = settings or load_settings()
    base = settings.get("compression", {}) or {}
    tools = settings.get("tools", {}) or {}
    specific = tools.get(tool_name) or tools.get("default") or {}
    return _deep_merge(base, specific if isinstance(specific, dict) else {})


def policy_summary(settings: Dict[str, Any] | None = None) -> Dict[str, Any]:
    settings = settings or load_settings()
    tools = settings.get("tools", {}) or {}
    out = []
    for tool_name in sorted(tools.keys()):
        policy = tool_policy(tool_name, settings)
        out.append({
            "tool_name": tool_name,
            "mode": policy.get("mode") or "preview_store",
            "min_chars": int(policy.get("min_chars") or 0),
            "preview_head_chars": int(policy.get("preview_head_chars") or 0),
            "preview_tail_chars": int(policy.get("preview_tail_chars") or 0),
            "enabled": bool((settings.get("compression", {}) or {}).get("enabled", True)),
        })
    return {
        "enabled": bool(settings.get("enabled", True)),
        "telemetry_enabled": bool((settings.get("telemetry", {}) or {}).get("enabled", True)),
        "compression_enabled": bool((settings.get("compression", {}) or {}).get("enabled", True)),
        "storage_enabled": bool((settings.get("storage", {}) or {}).get("enabled", True)),
        "retention_days": int((settings.get("storage", {}) or {}).get("retention_days") or 0),
        "tools": out,
    }
