from __future__ import annotations

import json
import math
from typing import Any


def to_text(result: Any) -> str:
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception:
        return str(result)


def estimate_tokens(text: str) -> int:
    # Rough multilingual estimate. Dashboard is for trend/savings, not billing precision.
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 3.6))


def safe_json_loads(text: str) -> Any | None:
    try:
        return json.loads(text)
    except Exception:
        return None
