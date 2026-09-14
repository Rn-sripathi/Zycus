"""Pipeline step 4: model-based compliance judgment.

Only runs where arithmetic cannot settle the question: qualitative rules, and
numeric rules whose number could not be extracted. Anything the numeric gate
already decided never reaches this step, so model judgment is used where it adds
value rather than everywhere.
"""

from __future__ import annotations

import logging

from app.domain.models import Clause, LLMAssessment, Rule
from app.llm.client import LLMClient, LLMError
from app.llm.prompts import COMPLIANCE_SCHEMA, COMPLIANCE_SYSTEM, build_compliance_prompt

logger = logging.getLogger(__name__)


async def check_compliance(clause: Clause, rule: Rule, client: LLMClient) -> LLMAssessment:
    """Judge one clause against one rule.

    A failed call returns a zero-confidence assessment rather than raising: the
    reviewer should see "this needs a human" instead of losing the clause entirely.
    """
    try:
        response = await client.complete_json(
            system_prompt=COMPLIANCE_SYSTEM,
            user_prompt=build_compliance_prompt(
                rule_block=_render_rule(rule),
                clause_block=clause.full_text,
            ),
            schema_name="compliance_assessment",
            schema=COMPLIANCE_SCHEMA,
        )
    except LLMError as exc:
        logger.warning("Compliance check failed for clause %s/%s: %s", clause.number, rule.id, exc)
        return LLMAssessment(
            violation=False,
            confidence=0.0,
            evidence_quote="",
            reasoning=(
                "Automated check could not be completed for this clause, so it needs a "
                "human reviewer."
            ),
        )

    return LLMAssessment(
        violation=bool(response.get("violation", False)),
        confidence=_clamp(response.get("confidence", 0.0)),
        evidence_quote=str(response.get("evidence_quote", "")).strip(),
        reasoning=str(response.get("reasoning", "")).strip(),
    )


def _render_rule(rule: Rule) -> str:
    return f"{rule.title}: {rule.text}\nWhy it matters: {rule.rationale}"


def _clamp(value: object) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, number))
