"""
In-memory session usage tracker for providers that don't expose a billing API.

Currently tracks Claude Code CLI token usage (input + output tokens, USD cost,
call count). Stats reset when the backend process restarts.

Usage:
    from backend.usage_tracker import record_claude_code, get_claude_code_stats
    record_claude_code(input_tokens=120, output_tokens=45, cost_usd=0.001)
    stats = get_claude_code_stats()
"""

import threading

_lock = threading.Lock()

_claude_code = {
    "calls": 0,
    "input_tokens": 0,
    "output_tokens": 0,
    "cost_usd": 0.0,
}


def record_claude_code(
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: float = 0.0,
) -> None:
    with _lock:
        _claude_code["calls"] += 1
        _claude_code["input_tokens"] += input_tokens
        _claude_code["output_tokens"] += output_tokens
        _claude_code["cost_usd"] += cost_usd


def get_claude_code_stats() -> dict:
    with _lock:
        return dict(_claude_code)
