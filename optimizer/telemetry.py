from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional

from .config import telemetry_db_path
from .util import estimate_tokens, to_text

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tool_result_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    session_id TEXT,
    task_id TEXT,
    tool_call_id TEXT,
    tool_name TEXT NOT NULL,
    duration_ms INTEGER,
    raw_chars INTEGER NOT NULL,
    raw_tokens INTEGER NOT NULL,
    compressed_chars INTEGER,
    compressed_tokens INTEGER,
    saved_tokens INTEGER,
    changed INTEGER DEFAULT 0,
    stored_path TEXT,
    status TEXT DEFAULT 'raw',
    compression_mode TEXT,
    evidence_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_tool_result_calls_ts ON tool_result_calls(ts);
CREATE INDEX IF NOT EXISTS idx_tool_result_calls_tool ON tool_result_calls(tool_name);
CREATE INDEX IF NOT EXISTS idx_tool_result_calls_call ON tool_result_calls(tool_call_id);
"""


def _connect() -> sqlite3.Connection:
    path = telemetry_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.executescript(_SCHEMA)
    _ensure_columns(conn)
    return conn


def _ensure_columns(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(tool_result_calls)").fetchall()}
    if "compression_mode" not in cols:
        conn.execute("ALTER TABLE tool_result_calls ADD COLUMN compression_mode TEXT")
    if "evidence_json" not in cols:
        conn.execute("ALTER TABLE tool_result_calls ADD COLUMN evidence_json TEXT")


def record_raw(*, tool_name: str, result: Any, task_id: str = "", session_id: str = "", tool_call_id: str = "", duration_ms: int = 0) -> None:
    text = to_text(result)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO tool_result_calls
            (ts, session_id, task_id, tool_call_id, tool_name, duration_ms, raw_chars, raw_tokens, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'raw')
            """,
            (time.time(), session_id, task_id, tool_call_id, tool_name, int(duration_ms or 0), len(text), estimate_tokens(text)),
        )


def record_compressed(*, tool_name: str, tool_call_id: str = "", raw_chars: int, raw_tokens: int, compressed_chars: int, compressed_tokens: int, changed: bool, stored_path: str = "", compressed_text: str = "") -> None:
    saved = max(0, int(raw_tokens or 0) - int(compressed_tokens or 0))
    evidence = _parse_compressed_text(compressed_text) if changed else {}
    compression_mode = evidence.get("compression_mode") or ("raw" if not changed else "preview_store")
    evidence_json = json.dumps(evidence, ensure_ascii=False) if evidence else ""
    with _connect() as conn:
        cur = conn.execute(
            """
            SELECT id FROM tool_result_calls
            WHERE tool_call_id = ? AND tool_name = ?
            ORDER BY id DESC LIMIT 1
            """,
            (tool_call_id, tool_name),
        )
        row = cur.fetchone()
        if row:
            conn.execute(
                """
                UPDATE tool_result_calls
                SET compressed_chars=?, compressed_tokens=?, saved_tokens=?, changed=?, stored_path=?, status='compressed', compression_mode=?, evidence_json=?
                WHERE id=?
                """,
                (compressed_chars, compressed_tokens, saved, 1 if changed else 0, stored_path, compression_mode, evidence_json, row[0]),
            )
        else:
            conn.execute(
                """
                INSERT INTO tool_result_calls
                (ts, tool_call_id, tool_name, raw_chars, raw_tokens, compressed_chars, compressed_tokens, saved_tokens, changed, stored_path, status, compression_mode, evidence_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'compressed', ?, ?)
                """,
                (time.time(), tool_call_id, tool_name, raw_chars, raw_tokens, compressed_chars, compressed_tokens, saved, 1 if changed else 0, stored_path, compression_mode, evidence_json),
            )


def _rows(rows: list[sqlite3.Row]) -> list[Dict[str, Any]]:
    return [dict(r) for r in rows]


def _parse_compressed_text(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    try:
        obj = json.loads(text)
    except Exception:
        return {}
    if not isinstance(obj, dict) or not obj.get("tool_result_optimized"):
        return {}
    mode = str(obj.get("compression_mode") or "preview_store")
    out: Dict[str, Any] = {"compression_mode": mode}
    if mode == "terminal_evidence":
        evidence = obj.get("evidence") if isinstance(obj.get("evidence"), dict) else obj
        out["terminal_status"] = evidence.get("status") or ""
        out["terminal_exit_code"] = evidence.get("exit_code")
    elif mode == "patch_diff_evidence":
        summary = obj.get("summary") if isinstance(obj.get("summary"), dict) else {}
        out["patch_files_changed"] = summary.get("files_changed")
        out["patch_hunks_omitted"] = summary.get("hunks_omitted")
        out["patch_syntax_check"] = summary.get("syntax_check") or ""
        markers: list[str] = []
        for item in obj.get("files") or []:
            if not isinstance(item, dict):
                continue
            for marker in item.get("risk_markers") or []:
                marker_s = str(marker)
                if marker_s and marker_s not in markers:
                    markers.append(marker_s)
        out["patch_risk_markers"] = ", ".join(markers[:12])
    return out


def _mode_for_row(row: Dict[str, Any]) -> str:
    if row.get("compression_mode"):
        return str(row["compression_mode"])
    if not row.get("changed"):
        return "raw"
    tool_name = str(row.get("tool_name") or "")
    if tool_name == "terminal":
        return "terminal_evidence"
    if tool_name == "patch":
        return "patch_diff_evidence"
    return "preview_store"


def _normalize_days(days: int | str | None = 1) -> int:
    try:
        value = int(days if days is not None else 1)
    except (TypeError, ValueError):
        value = 1
    allowed = {1, 3, 10, 30}
    return value if value in allowed else 1


def _where_since(days: int) -> tuple[str, tuple[float]]:
    from datetime import datetime, timedelta, timezone
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    since_epoch = (today - timedelta(days=(days - 1))).timestamp() if days > 0 else 0.0
    return "WHERE ts >= ?", (since_epoch,)


def summary(limit: int = 100, offset: int = 0, days: int = 3) -> Dict[str, Any]:
    limit = max(1, min(int(limit or 100), 500))
    offset = max(0, int(offset or 0))
    days = _normalize_days(days)
    where_sql, where_args = _where_since(days)
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        totals = conn.execute(
            f"""
            SELECT
              COUNT(*) AS calls,
              COALESCE(SUM(raw_tokens),0) AS raw_tokens,
              COALESCE(SUM(COALESCE(compressed_tokens, raw_tokens)),0) AS compressed_tokens,
              COALESCE(SUM(COALESCE(saved_tokens,0)),0) AS saved_tokens,
              COALESCE(SUM(changed),0) AS compressed_calls,
              COALESCE(AVG(duration_ms),0) AS avg_duration_ms
            FROM tool_result_calls
            {where_sql}
            """,
            where_args,
        ).fetchone()
        by_tool = conn.execute(
            f"""
            SELECT tool_name,
                   COALESCE(NULLIF(compression_mode,''), CASE WHEN changed THEN 'preview_store' ELSE 'raw' END) AS compression_mode,
                   COUNT(*) AS calls,
                   COALESCE(SUM(raw_tokens),0) AS raw_tokens,
                   COALESCE(SUM(COALESCE(compressed_tokens, raw_tokens)),0) AS compressed_tokens,
                   COALESCE(SUM(COALESCE(saved_tokens,0)),0) AS saved_tokens,
                   COALESCE(SUM(changed),0) AS compressed_calls,
                   COALESCE(AVG(duration_ms),0) AS avg_duration_ms
            FROM tool_result_calls
            {where_sql}
            GROUP BY tool_name, COALESCE(NULLIF(compression_mode,''), CASE WHEN changed THEN 'preview_store' ELSE 'raw' END)
            ORDER BY saved_tokens DESC, raw_tokens DESC
            LIMIT 50
            """,
            where_args,
        ).fetchall()
        recent = conn.execute(
            f"""
            SELECT id, ts, session_id, task_id, tool_call_id, tool_name, duration_ms,
                   raw_chars, raw_tokens,
                   COALESCE(compressed_chars, raw_chars) AS compressed_chars,
                   COALESCE(compressed_tokens, raw_tokens) AS compressed_tokens,
                   COALESCE(saved_tokens,0) AS saved_tokens,
                   changed, stored_path, status,
                   COALESCE(NULLIF(compression_mode,''), CASE WHEN changed THEN 'preview_store' ELSE 'raw' END) AS compression_mode,
                   evidence_json,
                   CASE WHEN raw_tokens > 0 THEN ROUND((COALESCE(saved_tokens,0) * 100.0) / raw_tokens, 2) ELSE 0 END AS savings_rate
            FROM tool_result_calls
            {where_sql}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            where_args + (limit, offset),
        ).fetchall()
        top_raw = conn.execute(
            f"""
            SELECT tool_name, COUNT(*) AS calls, COALESCE(SUM(raw_tokens),0) AS raw_tokens,
                   COALESCE(SUM(COALESCE(saved_tokens,0)),0) AS saved_tokens
            FROM tool_result_calls
            {where_sql}
            GROUP BY tool_name
            ORDER BY raw_tokens DESC
            LIMIT 10
            """,
            where_args,
        ).fetchall()
        top_saved = conn.execute(
            f"""
            SELECT id, ts, tool_name, raw_tokens, COALESCE(compressed_tokens, raw_tokens) AS compressed_tokens,
                   COALESCE(saved_tokens,0) AS saved_tokens, stored_path,
                   CASE WHEN raw_tokens > 0 THEN ROUND((COALESCE(saved_tokens,0) * 100.0) / raw_tokens, 2) ELSE 0 END AS savings_rate
            FROM tool_result_calls
            {where_sql}
            ORDER BY saved_tokens DESC, raw_tokens DESC
            LIMIT 10
            """,
            where_args,
        ).fetchall()
        by_mode = conn.execute(
            f"""
            SELECT COALESCE(NULLIF(compression_mode,''), CASE WHEN changed THEN 'preview_store' ELSE 'raw' END) AS compression_mode,
                   COUNT(*) AS calls,
                   COALESCE(SUM(raw_tokens),0) AS raw_tokens,
                   COALESCE(SUM(COALESCE(compressed_tokens, raw_tokens)),0) AS compressed_tokens,
                   COALESCE(SUM(COALESCE(saved_tokens,0)),0) AS saved_tokens,
                   COALESCE(SUM(changed),0) AS compressed_calls
            FROM tool_result_calls
            {where_sql}
            GROUP BY COALESCE(NULLIF(compression_mode,''), CASE WHEN changed THEN 'preview_store' ELSE 'raw' END)
            ORDER BY saved_tokens DESC, raw_tokens DESC
            """,
            where_args,
        ).fetchall()
        if days == 1:
            bucket_sql = "strftime('%Y-%m-%d %H:00', ts, 'unixepoch', 'localtime')"
        else:
            bucket_sql = "strftime('%Y-%m-%d', ts, 'unixepoch', 'localtime')"
        trend = conn.execute(
            f"""
            SELECT {bucket_sql} AS bucket,
                   COUNT(*) AS calls,
                   COALESCE(SUM(raw_tokens),0) AS raw_tokens,
                   COALESCE(SUM(COALESCE(compressed_tokens, raw_tokens)),0) AS compressed_tokens,
                   COALESCE(SUM(COALESCE(saved_tokens,0)),0) AS saved_tokens,
                   CASE WHEN SUM(raw_tokens) > 0 THEN ROUND(SUM(COALESCE(saved_tokens,0)) * 100.0 / SUM(raw_tokens), 2) ELSE 0 END AS savings_rate
            FROM tool_result_calls
            {where_sql}
            GROUP BY bucket
            ORDER BY bucket ASC
            """,
            where_args,
        ).fetchall()
        top_low_rate = conn.execute(
            f"""
            SELECT tool_name, COUNT(*) AS calls, COALESCE(SUM(raw_tokens),0) AS raw_tokens,
                   COALESCE(SUM(COALESCE(saved_tokens,0)),0) AS saved_tokens,
                   CASE WHEN SUM(raw_tokens) > 0 THEN ROUND((SUM(COALESCE(saved_tokens,0)) * 100.0) / SUM(raw_tokens), 2) ELSE 0 END AS savings_rate
            FROM tool_result_calls
            {where_sql}
            GROUP BY tool_name
            HAVING raw_tokens >= 1000
            ORDER BY savings_rate ASC, raw_tokens DESC
            LIMIT 10
            """,
            where_args,
        ).fetchall()
        top_calls = conn.execute(
            f"""
            SELECT tool_name, COUNT(*) AS calls, COALESCE(SUM(raw_tokens),0) AS raw_tokens,
                   COALESCE(SUM(COALESCE(saved_tokens,0)),0) AS saved_tokens
            FROM tool_result_calls
            {where_sql}
            GROUP BY tool_name
            ORDER BY calls DESC, raw_tokens DESC
            LIMIT 10
            """,
            where_args,
        ).fetchall()
        recent_total = conn.execute(
            f"SELECT COUNT(*) FROM tool_result_calls {where_sql}",
            where_args,
        ).fetchone()[0]
    recent_rows = _rows(recent)
    for row in recent_rows:
        evidence: Dict[str, Any] = {}
        try:
            evidence = json.loads(row.get("evidence_json") or "{}")
        except Exception:
            evidence = {}
        row["compression_mode"] = _mode_for_row(row)
        if evidence:
            row.update({k: v for k, v in evidence.items() if k != "compression_mode"})
        row.pop("evidence_json", None)
    return {
        "totals": dict(totals) if totals else {},
        "by_tool": _rows(by_tool),
        "by_mode": _rows(by_mode),
        "trend": _rows(trend),
        "recent": recent_rows,
        "recent_total": recent_total,
        "days": days,
        "rankings": {
            "top_raw_tools": _rows(top_raw),
            "top_saved_calls": _rows(top_saved),
            "low_savings_tools": _rows(top_low_rate),
            "top_called_tools": _rows(top_calls),
        },
        "db_path": str(telemetry_db_path()),
    }
