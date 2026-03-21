"""
backend/logging_config.py — Structured JSON logging for Poly-QL.

Replaces the default line-based format with a JSON log line per record so that
log aggregators (Datadog, CloudWatch, Loki, etc.) can parse fields without
custom grok patterns.

Usage
-----
    from backend.logging_config import configure_logging
    configure_logging()          # call once at startup
"""
import json
import logging
import time


class _JsonFormatter(logging.Formatter):
    """Emit every log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Attach any extra fields passed via extra={} in logger calls
        for key, val in record.__dict__.items():
            if key not in logging.LogRecord.__init__.__code__.co_varnames and key not in (
                "msg", "args", "levelname", "levelno", "pathname", "filename",
                "module", "exc_info", "exc_text", "stack_info", "lineno",
                "funcName", "created", "msecs", "relativeCreated", "thread",
                "threadName", "processName", "process", "name", "message",
                "taskName",
            ):
                try:
                    json.dumps(val)   # only include JSON-serialisable extras
                    payload[key] = val
                except (TypeError, ValueError):
                    payload[key] = str(val)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> None:
    """
    Configure the root logger with a JSON formatter.

    Call once at application startup.  Subsequent calls are no-ops (guards
    against duplicate handler registration if modules are reloaded in tests).
    """
    root = logging.getLogger()
    # Avoid adding duplicate handlers when called multiple times (e.g. in tests)
    if any(isinstance(h, logging.StreamHandler) and isinstance(getattr(h, "formatter", None), _JsonFormatter)
           for h in root.handlers):
        return

    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    root.setLevel(level)
    root.addHandler(handler)
