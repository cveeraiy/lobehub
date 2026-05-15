"""Agent evaluation service — run evals against agent outputs.

Mirrors TS ``agentEvalRun/`` service.
"""

from app.services.agent_eval.service import AgentEvalService

__all__ = ["AgentEvalService"]
