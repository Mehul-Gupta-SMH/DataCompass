"""
Balance / credit checker for each configured LLM provider.

Each checker returns:
  {
    "balance":   float | None,   # dollar amount, None if unavailable
    "currency":  str   | None,   # "USD" or None
    "available": bool,           # False  → grey out in UI
    "status":    str,            # "ok" | "no_balance" | "invalid_key" | "unavailable"
    "label":     str,            # human-readable string for the dropdown
  }

Only OpenAI exposes a public credit-balance API.
For Anthropic / Google / GROQ we probe with a lightweight auth check
(HEAD / models-list request) to detect invalid keys, and report N/A otherwise.
"""

import sys
import os
import json
import logging
import subprocess
import yaml
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from Utilities.base_utils import get_config_val

logger = logging.getLogger(__name__)

_TIMEOUT = 8   # seconds per request


# ---------------------------------------------------------------------------
# Shared key loader
# ---------------------------------------------------------------------------

def _load_api_key(provider: str) -> str | None:
    """Return the API key for *provider* from model_access_config.YAML, or None."""
    try:
        model_config_path = get_config_val("model_config", ["model_config", "path"])
        with open(model_config_path, "r") as f:
            cfg = yaml.load(f, yaml.FullLoader)
        return cfg[provider.upper()].get("api_key")
    except Exception as exc:
        logger.debug("Could not load api_key for %s: %s", provider, exc)
        return None


# ---------------------------------------------------------------------------
# Provider-specific checkers
# ---------------------------------------------------------------------------

def _check_openai(api_key: str) -> dict:
    """
    Try OpenAI's credit-grants / organization-credits endpoints.
    Returns confirmed dollar balance when available.
    Greys out on 401 (invalid key) or confirmed $0 balance.

    Note: dashboard/billing endpoints require a browser session key and return
    403 for secret (sk-...) keys. We fall back to a models-list probe to at
    least confirm key validity.
    """
    auth = {"Authorization": f"Bearer {api_key}"}
    saw_invalid_key = False

    for url in [
        "https://api.openai.com/v1/organization/credits",
        "https://api.openai.com/v1/dashboard/billing/credit_grants",
    ]:
        try:
            r = requests.get(url, headers=auth, timeout=_TIMEOUT)
        except requests.RequestException:
            continue

        if r.status_code == 401:
            saw_invalid_key = True
            continue

        if r.status_code == 200:
            data = r.json()
            # newer endpoint: {"total_available": 5.0, ...}
            # legacy endpoint: {"total_available": 5.0, "total_used": ..., ...}
            raw = data.get("total_available")
            if raw is None:
                # Some accounts return {"data": [...], ...}
                grants = data.get("data", [])
                if grants:
                    raw = sum(g.get("grant_amount", 0) - g.get("used_amount", 0)
                              for g in grants)
            if raw is not None:
                amt = round(float(raw), 2)
                if amt <= 0:
                    return {"balance": 0.0, "currency": "USD",
                            "available": False, "status": "no_balance",
                            "label": "$0.00"}
                return {"balance": amt, "currency": "USD",
                        "available": True, "status": "ok",
                        "label": f"${amt:,.2f}"}

    if saw_invalid_key:
        return {"balance": None, "currency": "USD",
                "available": False, "status": "invalid_key", "label": "Invalid key"}

    # Balance API not accessible for secret keys (requires browser session).
    # Fall back to a lightweight models-list call to confirm key validity.
    try:
        r = requests.get(
            "https://api.openai.com/v1/models",
            headers=auth,
            timeout=_TIMEOUT,
        )
        if r.status_code == 401:
            return {"balance": None, "currency": "USD",
                    "available": False, "status": "invalid_key", "label": "Invalid key"}
    except requests.RequestException:
        pass

    return {"balance": None, "currency": "USD",
            "available": True, "status": "unavailable", "label": "N/A"}


def _check_anthropic(api_key: str) -> dict:
    """
    Anthropic has no public balance API.
    1. GET /v1/models  — detects invalid keys (401).
    2. POST /v1/messages (max_tokens=1) — detects exhausted credits (400 billing error).
    """
    headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}

    # Step 1: key validity
    try:
        r = requests.get(
            "https://api.anthropic.com/v1/models",
            headers=headers,
            timeout=_TIMEOUT,
        )
        if r.status_code == 401:
            return {"balance": None, "currency": None,
                    "available": False, "status": "invalid_key", "label": "Invalid key"}
    except requests.RequestException:
        pass

    # Step 2: credit availability — a 1-token probe catches billing errors cheaply
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={**headers, "Content-Type": "application/json"},
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "hi"}],
            },
            timeout=_TIMEOUT,
        )
        if r.status_code == 400:
            msg = (r.json().get("error") or {}).get("message", "").lower()
            if "credit" in msg or "billing" in msg or "balance" in msg:
                return {"balance": 0.0, "currency": None,
                        "available": False, "status": "no_balance", "label": "No credits"}
    except requests.RequestException:
        pass

    return {"balance": None, "currency": None,
            "available": True, "status": "unavailable", "label": "N/A"}


def _check_groq(api_key: str) -> dict:
    """
    GROQ has no public balance API.
    Probe /openai/v1/models to detect invalid keys.
    """
    try:
        r = requests.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=_TIMEOUT,
        )
        if r.status_code == 401:
            return {"balance": None, "currency": None,
                    "available": False, "status": "invalid_key", "label": "Invalid key"}
    except requests.RequestException:
        pass

    return {"balance": None, "currency": None,
            "available": True, "status": "unavailable", "label": "N/A"}


def _check_google(api_key: str) -> dict:
    """
    Google AI / Gemini has no public balance API.
    Probe the models endpoint to detect invalid keys.
    """
    try:
        r = requests.get(
            f"https://generativelanguage.googleapis.com/v1/models?key={api_key}",
            timeout=_TIMEOUT,
        )
        if r.status_code in (400, 401, 403):
            data = r.json()
            err = (data.get("error") or {}).get("status", "")
            if err in ("INVALID_ARGUMENT", "UNAUTHENTICATED", "PERMISSION_DENIED"):
                return {"balance": None, "currency": None,
                        "available": False, "status": "invalid_key", "label": "Invalid key"}
    except requests.RequestException:
        pass

    return {"balance": None, "currency": None,
            "available": True, "status": "unavailable", "label": "N/A"}


def _check_claude_code(_api_key: str) -> dict:
    """
    claude_code uses the local Claude Code CLI, not an API key.
    Check that the `claude` executable is installed and show session token usage
    accumulated since the backend started.
    """
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            version = result.stdout.strip().split("\n")[0]

            # Include session usage if any calls have been made
            try:
                from backend.usage_tracker import get_claude_code_stats
                stats = get_claude_code_stats()
                if stats["calls"] > 0:
                    tok_in  = stats["input_tokens"]
                    tok_out = stats["output_tokens"]
                    cost    = stats["cost_usd"]
                    usage_str = (
                        f"{tok_in:,}↑ {tok_out:,}↓ tok"
                        + (f" · ${cost:.4f}" if cost > 0 else "")
                    )
                    label = f"CLI {version} · {usage_str}"
                else:
                    label = f"CLI {version}"
            except Exception:
                label = f"CLI {version}"

            return {"balance": None, "currency": None,
                    "available": True, "status": "ok", "label": label}
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        pass

    return {"balance": None, "currency": None,
            "available": False, "status": "unavailable",
            "label": "CLI not installed"}


_CHECKERS = {
    "open_ai":    _check_openai,
    "anthropic":  _check_anthropic,
    "groq":       _check_groq,
    "google":     _check_google,
    "codex":      _check_openai,       # same OpenAI key / billing as open_ai
    "claude_code": _check_claude_code, # CLI availability check — no API key needed
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_all_balances(providers: list) -> dict:
    """
    Fetch balance / validity info for every provider concurrently.
    Returns {provider: {balance, currency, available, status, label}}.
    Unreachable or misconfigured providers get {available: True, label: "N/A"}
    so they are never incorrectly greyed out.
    """
    results = {}

    def _check_one(provider):
        api_key = _load_api_key(provider)
        if not api_key:
            return provider, {"balance": None, "currency": None,
                              "available": True, "status": "no_config", "label": "N/A"}
        checker = _CHECKERS.get(provider)
        if checker is None:
            return provider, {"balance": None, "currency": None,
                              "available": True, "status": "unavailable", "label": "N/A"}
        try:
            return provider, checker(api_key)
        except Exception as exc:
            logger.warning("Balance check failed for %s: %s", provider, exc)
            return provider, {"balance": None, "currency": None,
                              "available": True, "status": "error", "label": "N/A"}

    with ThreadPoolExecutor(max_workers=len(providers) or 1) as pool:
        futures = {pool.submit(_check_one, p): p for p in providers}
        for future in as_completed(futures):
            provider, info = future.result()
            results[provider] = info

    return results
