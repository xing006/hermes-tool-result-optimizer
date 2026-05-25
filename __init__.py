from __future__ import annotations

from .optimizer.hooks import post_tool_call, transform_tool_result


def register(ctx):
    ctx.register_hook("post_tool_call", post_tool_call)
    ctx.register_hook("transform_tool_result", transform_tool_result)
