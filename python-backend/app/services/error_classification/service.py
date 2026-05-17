"""Tool error classification — port of TS ``toolExecution/errorClassification.ts``.

Classifies tool execution errors into one of three kinds:
- **replan**: The LLM should adjust arguments or try a different tool.
- **retry**: Transient failure; safe to retry the same call.
- **stop**: Fatal / permission error; halt execution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal, Optional

ToolErrorKind = Literal["replan", "retry", "stop"]

# ---------------------------------------------------------------------------
# Code sets
# ---------------------------------------------------------------------------

RETRY_CODES = frozenset({
    "RATE_LIMITED", "SERVICE_UNAVAILABLE", "TOO_MANY_REQUESTS",
})
REPLAN_CODES = frozenset({
    "BAD_REQUEST", "INVALID_ARGUMENT", "MANIFEST_NOT_FOUND",
    "MCP_CONFIG_NOT_FOUND", "MCP_EXECUTION_ERROR",
})
STOP_CODES = frozenset({
    "FORBIDDEN", "INSUFFICIENT_PERMISSIONS", "NOT_IMPLEMENTED",
    "PERMISSION_DENIED", "UNAUTHORIZED",
})

# ---------------------------------------------------------------------------
# Keyword sets
# ---------------------------------------------------------------------------

RETRY_KEYWORDS = [
    "timeout", "timed out", "too many requests",
    "temporarily unavailable", "service unavailable",
    "network", "socket hang up", "econnreset",
    "econnrefused", "enotfound",
]
REPLAN_KEYWORDS = [
    "invalid", "malformed", "schema", "parse",
    "not found", "missing required", "manifest not found",
    "not implemented",
]
STOP_KEYWORDS = [
    "unauthorized", "forbidden", "permission denied",
    "api key", "quota", "billing", "not configured",
]


def _has_any_keyword(text: str, keywords: list[str]) -> bool:
    return any(kw in text for kw in keywords)


def _normalize_code(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return re.sub(r"[\s-]+", "_", value.strip().upper())


def _try_extract_status(message: str) -> Optional[int]:
    m = re.search(r"\b([45]\d{2})\b", message)
    if not m:
        return None
    status = int(m.group(1))
    return status


# ---------------------------------------------------------------------------
# Signal normalization
# ---------------------------------------------------------------------------

@dataclass
class _ToolErrorSignal:
    message: str
    code: Optional[str] = None
    status: Optional[int] = None


def _normalize_signal(error: Any) -> _ToolErrorSignal:
    if isinstance(error, str):
        message = error.lower()
        return _ToolErrorSignal(message=message, status=_try_extract_status(message))

    if isinstance(error, Exception):
        message = (str(error) or type(error).__name__ or "unknown error").lower()
        code = _normalize_code(getattr(error, "code", None))
        status = getattr(error, "status", None) or getattr(error, "status_code", None)
        if isinstance(status, int):
            pass
        else:
            status = _try_extract_status(message)
        return _ToolErrorSignal(message=message, code=code, status=status)

    if isinstance(error, dict):
        nested = error.get("error", {})
        nested_code = nested.get("code") if isinstance(nested, dict) else None
        nested_msg = nested.get("message") if isinstance(nested, dict) else None
        message = (error.get("message") or nested_msg or "unknown error").lower()

        raw_code = error.get("code") or nested_code
        code = _normalize_code(raw_code) if raw_code else None

        status = error.get("status") or error.get("statusCode")
        if not isinstance(status, int) and isinstance(nested, dict):
            status = nested.get("status") or nested.get("statusCode")
        if not isinstance(status, int):
            status = _try_extract_status(message)

        return _ToolErrorSignal(message=message, code=code, status=status if isinstance(status, int) else None)

    return _ToolErrorSignal(message="unknown error")


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def _classify_kind(signal: _ToolErrorSignal) -> ToolErrorKind:
    if signal.code:
        if signal.code in STOP_CODES:
            return "stop"
        if signal.code in REPLAN_CODES:
            return "replan"
        if signal.code in RETRY_CODES:
            return "retry"

    if signal.status is not None:
        if signal.status in (401, 403):
            return "stop"
        if signal.status in (400, 404, 409, 422):
            return "replan"
        if signal.status in (408, 425, 429) or signal.status >= 500:
            return "retry"

    if _has_any_keyword(signal.message, STOP_KEYWORDS):
        return "stop"
    if _has_any_keyword(signal.message, REPLAN_KEYWORDS):
        return "replan"
    if _has_any_keyword(signal.message, RETRY_KEYWORDS):
        return "retry"

    # Unknown failures may happen after a side effect already succeeded,
    # so only explicitly classified retryable errors should be replayed.
    return "stop"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class ClassifiedToolError:
    kind: ToolErrorKind
    message: str
    code: Optional[str] = None


def classify_tool_error(error: Any) -> ClassifiedToolError:
    """Classify a tool execution error into replan / retry / stop."""
    signal = _normalize_signal(error)
    return ClassifiedToolError(
        kind=_classify_kind(signal),
        message=signal.message,
        code=signal.code,
    )
