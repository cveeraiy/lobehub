"""Task Review Service — automated scoring/review of task outputs.

Ports TS ``taskReview/index.ts``:
- LLM-based rubric evaluation of task outputs
- Configurable judge model/provider
- Per-rubric scoring with pass/fail determination
- Iteration tracking for retry loops
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass
class ReviewJudge:
    """Model configuration for the review judge."""
    model: Optional[str] = None
    provider: Optional[str] = None
    prompt: Optional[str] = None


@dataclass
class EvalRubric:
    """A single evaluation rubric."""
    name: str
    description: str
    weight: float = 1.0
    type: str = "llm"  # "llm" | "keyword" | "regex"
    criteria: Optional[str] = None
    pass_threshold: float = 0.6


@dataclass
class RubricResult:
    """Result for a single rubric evaluation."""
    name: str
    score: float  # 0.0 - 1.0
    passed: bool
    reasoning: str = ""
    weight: float = 1.0


@dataclass
class ReviewResult:
    """Full review result."""
    iteration: int
    overall_score: int  # 0-100
    passed: bool
    rubric_results: list[RubricResult] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


@dataclass
class ReviewConfig:
    """Configuration for task review."""
    enabled: bool = True
    auto_retry: bool = False
    max_iterations: int = 3
    judge: ReviewJudge = field(default_factory=ReviewJudge)
    rubrics: list[EvalRubric] = field(default_factory=list)


# Default model config
_DEFAULT_JUDGE_MODEL = "gpt-4o-mini"
_DEFAULT_JUDGE_PROVIDER = "openai"
_DEFAULT_PASS_THRESHOLD = 0.6


class TaskReviewService:
    """Automated review/scoring of task outputs using LLM-based rubrics."""

    def __init__(self, session: AsyncSession, user_id: str) -> None:
        self._db = session
        self._uid = user_id

    async def review(
        self,
        *,
        content: str,
        task_name: str,
        rubrics: list[EvalRubric],
        judge: ReviewJudge,
        iteration: int = 1,
    ) -> ReviewResult:
        """Evaluate task output against rubrics.

        Args:
            content: The task output to evaluate.
            task_name: Human-readable task name for context.
            rubrics: List of evaluation rubrics.
            judge: Model/provider config for the judge LLM.
            iteration: Current retry iteration number.

        Returns:
            ReviewResult with per-rubric scores and overall pass/fail.
        """
        model_config = await self._resolve_model_config(judge)
        model_str = f"{model_config['provider']}/{model_config['model']}"

        logger.info(
            "Starting review for task %r (iteration %d, model=%s, rubrics=%d)",
            task_name, iteration, model_str, len(rubrics),
        )

        rubric_results: list[RubricResult] = []

        for rubric in rubrics:
            if rubric.type == "llm":
                result = await self._evaluate_llm_rubric(
                    content=content,
                    task_name=task_name,
                    rubric=rubric,
                    model_str=model_str,
                    judge_prompt=judge.prompt,
                )
            elif rubric.type == "keyword":
                result = self._evaluate_keyword_rubric(content, rubric)
            else:
                result = RubricResult(
                    name=rubric.name,
                    score=0.0,
                    passed=False,
                    reasoning=f"Unknown rubric type: {rubric.type}",
                    weight=rubric.weight,
                )
            rubric_results.append(result)

        # Calculate weighted overall score
        total_weight = sum(r.weight for r in rubric_results)
        if total_weight > 0:
            weighted_score = sum(r.score * r.weight for r in rubric_results) / total_weight
        else:
            weighted_score = 0.0

        overall_score = round(weighted_score * 100)
        passed = weighted_score >= _DEFAULT_PASS_THRESHOLD

        logger.info(
            "Review complete: %r (score: %d, passed: %s)",
            task_name, overall_score, passed,
        )

        # Extract suggestions from failed rubrics
        suggestions = [
            f"[{r.name}] {r.reasoning}"
            for r in rubric_results
            if not r.passed and r.reasoning
        ]

        return ReviewResult(
            iteration=iteration,
            overall_score=overall_score,
            passed=passed,
            rubric_results=rubric_results,
            suggestions=suggestions,
        )

    # ── Private ───────────────────────────────────────────────────────

    async def _evaluate_llm_rubric(
        self,
        *,
        content: str,
        task_name: str,
        rubric: EvalRubric,
        model_str: str,
        judge_prompt: Optional[str] = None,
    ) -> RubricResult:
        """Evaluate a single rubric using LLM as judge."""
        try:
            criteria = rubric.criteria or rubric.description

            base_prompt = judge_prompt or (
                "You are an expert evaluator. Score the following task output "
                "against the given criteria."
            )

            system_prompt = (
                f"{base_prompt}\n\n"
                f"Task: {task_name}\n"
                f"Rubric: {rubric.name}\n"
                f"Criteria: {criteria}\n\n"
                f"Score from 0.0 to 1.0 where 1.0 is perfect.\n"
                f"Respond with JSON: {{\"score\": <float>, \"reasoning\": \"<explanation>\"}}"
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Task output to evaluate:\n\n{content[:8000]}"},
            ]

            from app.services import llm_service

            response = await llm_service.chat(
                messages,
                model=model_str,
                stream=False,
                temperature=0.1,
                max_tokens=300,
                extra_kwargs={"response_format": {"type": "json_object"}},
            )

            result_text = response.choices[0].message.content or "{}"
            data = json.loads(result_text)
            score = max(0.0, min(1.0, float(data.get("score", 0))))
            reasoning = str(data.get("reasoning", ""))

            return RubricResult(
                name=rubric.name,
                score=score,
                passed=score >= rubric.pass_threshold,
                reasoning=reasoning,
                weight=rubric.weight,
            )

        except Exception as exc:
            logger.warning("LLM rubric evaluation failed for %r: %s", rubric.name, exc)
            return RubricResult(
                name=rubric.name,
                score=0.0,
                passed=False,
                reasoning=f"Evaluation failed: {exc}",
                weight=rubric.weight,
            )

    @staticmethod
    def _evaluate_keyword_rubric(content: str, rubric: EvalRubric) -> RubricResult:
        """Evaluate a keyword-based rubric (simple string matching)."""
        criteria = rubric.criteria or ""
        keywords = [k.strip().lower() for k in criteria.split(",") if k.strip()]

        if not keywords:
            return RubricResult(
                name=rubric.name,
                score=0.0,
                passed=False,
                reasoning="No keywords specified in criteria",
                weight=rubric.weight,
            )

        content_lower = content.lower()
        found = sum(1 for kw in keywords if kw in content_lower)
        score = found / len(keywords)

        missing = [kw for kw in keywords if kw not in content_lower]
        reasoning = (
            f"Found {found}/{len(keywords)} keywords."
            + (f" Missing: {', '.join(missing)}" if missing else "")
        )

        return RubricResult(
            name=rubric.name,
            score=score,
            passed=score >= rubric.pass_threshold,
            reasoning=reasoning,
            weight=rubric.weight,
        )

    async def _resolve_model_config(
        self,
        judge: ReviewJudge,
    ) -> dict[str, str]:
        """Resolve model/provider, falling back to user settings or defaults."""
        if judge.model and judge.provider:
            return {"model": judge.model, "provider": judge.provider}

        try:
            from app.models.user import UserSettings
            stmt = select(UserSettings).where(UserSettings.id == self._uid)
            result = await self._db.execute(stmt)
            setting = result.scalar_one_or_none()

            if setting and setting.system_agent:
                topic_config = setting.system_agent.get("topic", {})
                return {
                    "model": judge.model or topic_config.get("model") or _DEFAULT_JUDGE_MODEL,
                    "provider": judge.provider or topic_config.get("provider") or _DEFAULT_JUDGE_PROVIDER,
                }
        except Exception:
            pass

        return {
            "model": judge.model or _DEFAULT_JUDGE_MODEL,
            "provider": judge.provider or _DEFAULT_JUDGE_PROVIDER,
        }
