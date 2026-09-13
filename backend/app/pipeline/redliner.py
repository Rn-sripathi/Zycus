"""Pipeline step 5: draft replacement language for a confirmed deviation.

Runs only for clauses already established as deviating, so the model is asked to
write rather than to judge. The playbook's own redline guidance is passed in, which
keeps the drafting close to house position instead of generic contract boilerplate.
"""

from __future__ import annotations

import logging

from app.domain.models import Clause, Rule
from app.llm.client import LLMClient, LLMError
from app.llm.prompts import REDLINE_SCHEMA, REDLINE_SYSTEM, build_redline_prompt

logger = logging.getLogger(__name__)


async def draft_redline(
    clause: Clause,
    rule: Rule,
    problem: str,
    client: LLMClient,
) -> tuple[str, str]:
    """Return ``(proposed_redline, change_summary)`` for a deviating clause."""
    try:
        response = await client.complete_json(
            system_prompt=REDLINE_SYSTEM,
            user_prompt=build_redline_prompt(
                rule_block=_render_rule(rule),
                clause_block=clause.full_text,
                problem=problem,
            ),
            schema_name="redline_draft",
            schema=REDLINE_SCHEMA,
            temperature=0.2,  # a little room to phrase naturally, not to invent terms
        )
    except LLMError as exc:
        logger.warning("Redline drafting failed for clause %s/%s: %s", clause.number, rule.id, exc)
        return "", ""

    return (
        str(response.get("proposed_redline", "")).strip(),
        str(response.get("change_summary", "")).strip(),
    )


def _render_rule(rule: Rule) -> str:
    block = f"{rule.title}: {rule.text}\nWhy it matters: {rule.rationale}"
    if rule.redline_guidance:
        block += f"\nHouse position: {rule.redline_guidance}"
    return block
