"""Agent Signal — event-driven agent orchestration pipeline.

Python owns the server-side Agent Signal architecture:
- ``SignalSource``   — emits signals from external events (cron, webhook, etc.)
- ``SignalPolicy``   — routing rules, dedup, scope
- ``SignalProcessor``— handles a signal by invoking agent actions
- ``Orchestrator``   — wires sources → policies → processors
"""

from app.services.agent_signal.types import Signal, SignalAction, SignalPolicy
from app.services.agent_signal.orchestrator import SignalOrchestrator, get_orchestrator

__all__ = [
    "Signal",
    "SignalAction",
    "SignalPolicy",
    "SignalOrchestrator",
    "get_orchestrator",
]
