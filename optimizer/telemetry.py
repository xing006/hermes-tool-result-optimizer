from __future__ import annotations

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
    status TEXT DEFAULT 'raw'
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
    return conn


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


def record_compressed(*, tool_name: str, tool_call_id: str = "", raw_chars: int, raw_tokens: int, compressed_chars: int, compressed_tokens: int, changed: bool, stored_path: str = "") -> None:
    saved = max(0, int(raw_tokens or 0) - int(compressed_tokens or 0))
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
                SET compressed_chars=?, compressed_tokens=?, saved_tokens=?, changed=?, stored_path=?, status='compressed'
                WHERE id=?
                """,
                (compressed_chars, compressed_tokens, saved, 1 if changed else 0, stored_path, row[0]),
            )
        else:
            conn.execute(
                """
                INSERT INTO tool_result_calls
                (ts, tool_call_id, tool_name, raw_chars, raw_tokens, compressed_chars, compressed_tokens, saved_tokens, changed, stored_path, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'compressed')
                """,
                (time.time(), tool_call_id, tool_name, raw_chars, raw_tokens, compressed_chars, compressed_tokens, saved, 1 if changed else 0, stored_path),
            )


def _rows(rows: list[sqlite3.Row]) -> list[Dict[str, Any]]:
    return [dict(r) for r in rows]


def summary(limit: int = 100) -> Dict[str, Any]:
    limit = max(1, min(int(limit or 100), 500))
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        totals = conn.execute(
            """
            SELECT
              COUNT(*) AS calls,
              COALESCE(SUM(raw_tokens),0) AS raw_tokens,
              COALESCE(SUM(COALESCE(compressed_tokens, raw_tokens)),0) AS compressed_tokens,
              COALESCE(SUM(COALESCE(saved_tokens,0)),0) AS saved_tokens,
              COALESCE(SUM(changed),0) AS compressed_calls,
              COALESCE(AVG(duration_ms),0) AS avg_duration_ms
            FROM tool_result_calls
            """
        ).fetchone()
        by_tool = conn.execute(
            """
            SELECT tool_name,
                   COUNT(*) AS calls,
                   COALESCE(SUM(raw_tokens),0) AS raw_tokens,
                   COALESCE(SUM(COALESCE(compressed_tokens, raw_tokens)),0) AS compressed_tokens,
                   COALESCE(SUM(COALESCE(saved_tokens,0)),0) AS saved_tokens,
                   COALESCE(SUM(changed),0) AS compressed_calls,
                   COALESCE(AVG(duration_ms),0) AS avg_duration_ms
            FROM tool_result_calls
            GROUP BY tool_name
            ORDER BY saved_tokens DESC, raw_tokens DESC
            LIMIT 50
            """
        ).fetchall()
        recent = conn.execute(
            """
            SELECT id, ts, session_id, task_id, tool_call_id, tool_name, duration_ms,
                   raw_chars, raw_tokens,
                   COALESCE(compressed_chars, raw_chars) AS compressed_chars,
                   COALESCE(compressed_tokens, raw_tokens) AS compressed_tokens,
                   COALESCE(saved_tokens,0) AS saved_tokens,
                   changed, stored_path, status,
                   CASE WHEN raw_tokens > 0 THEN ROUND((COALESCE(saved_tokens,0) * 100.0) / raw_tokens, 2) ELSE 0 END AS savings_rate
            FROM tool_result_calls
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        top_raw = conn.execute(
            """
            SELECT tool_name, COUNT(*) AS calls, COALESCE(SUM(raw_tokens),0) AS raw_tokens,
                   COALESCE(SUM(COALESCE(saved_tokens,0)),0) AS saved_tokens
            FROM tool_result_calls
            GROUP BY tool_name
            ORDER BY raw_tokens DESC
            LIMIT 10
            """
        ).fetchall()
        top_saved = conn.execute(
            """
            SELECT id, ts, tool_name, raw_tokens, COALESCE(compressed_tokens, raw_tokens) AS compressed_tokens,
                   COALESCE(saved_tokens,0) AS saved_tokens, stored_path,
                   CASE WHEN raw_tokens > 0 THEN ROUND((COALESCE(saved_tokens,0) * 100.0) / raw_tokens, 2) ELSE 0 END AS savings_rate
            FROM tool_result_calls
            ORDER BY saved_tokens DESC, raw_tokens DESC
            LIMIT 10
            """
        ).fetchall()
        top_low_rate = conn.execute(
            """
            SELECT tool_name, COUNT(*) AS calls, COALESCE(SUM(raw_tokens),0) AS raw_tokens,
                   COALESCE(SUM(COALESCE(saved_tokens,0)),0) AS saved_tokens,
                   CASE WHEN SUM(raw_tokens) > 0 THEN ROUND((SUM(COALESCE(saved_tokens,0)) * 100.0) / SUM(raw_tokens), 2) ELSE 0 END AS savings_rate
            FROM tool_result_calls
            GROUP BY tool_name
            HAVING raw_tokens >= 1000
            ORDER BY savings_rate ASC, raw_tokens DESC
            LIMIT 10
            """
        ).fetchall()
        top_calls = conn.execute(
            """
            SELECT tool_name, COUNT(*) AS calls, COALESCE(SUM(raw_tokens),0) AS raw_tokens,
                   COALESCE(SUM(COALESCE(saved_tokens,0)),0) AS saved_tokens
            FROM tool_result_calls
            GROUP BY tool_name
            ORDER BY calls DESC, raw_tokens DESC
            LIMIT 10
            """
        ).fetchall()
    return {
        "totals": dict(totals) if totals else {},
        "by_tool": _rows(by_tool),
        "recent": _rows(recent),
        "rankings": {
            "top_raw_tools": _rows(top_raw),
            "top_saved_calls": _rows(top_saved),
            "low_savings_tools": _rows(top_low_rate),
            "top_called_tools": _rows(top_calls),
        },
        "db_path": str(telemetry_db_path()),
    }
