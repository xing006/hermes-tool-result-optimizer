from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


def _plugin_root_on_path() -> None:
    from pathlib import Path
    import sys

    plugin_root = Path(__file__).resolve().parents[1]
    if str(plugin_root) not in sys.path:
        sys.path.insert(0, str(plugin_root))


@router.get("/summary")
async def get_summary(limit: int = 100, offset: int = 0):
    _plugin_root_on_path()
    from optimizer.telemetry import summary

    return summary(limit=limit, offset=offset)


@router.get("/policy")
async def get_policy():
    _plugin_root_on_path()
    from optimizer.config import policy_summary

    return policy_summary()
