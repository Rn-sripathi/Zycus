"""Pipeline step 5: draft replacement language for a clause's deviations.

Drafting happens per CLAUSE, not per rule. A clause can breach several rules at
once -- clause 1 of the sample contract breaches two -- and drafting each fix in
isolation produces replacements that each repair one problem while silently
preserving the other. Since both are full replacements of the same clause, they
also cannot be applied together: pasting either one ships a known violation.

So every rule a clause breaches goes into one drafting call, and the resulting
text has to satisfy all of them.
"""

from __future__ import annotations

import logging

from app.domain.models import Clause, Rule
from app.llm.client import LLMClient, LLMError
from app.llm.prompts import REDLINE_SCHEMA, REDLINE_SYSTEM, build_redline_prompt

logger = logging.getLogger(__name__)


async def draft_redline(
    clause: Clause,
    issues: list[tuple[Rule, str]],
    client: LLMClient,
) -> tuple[str, str]:
    """Draft one replacement for ``clause`` covering every issue in ``issues``.

    ``issues`` pairs each breached rule with a description of how the clause fails
    it. Returns ``(proposed_redline, change_summary)``.
    """
    if not issues:
        return "", ""

    try:
        response = await client.complete_json(
            system_prompt=REDLINE_SYSTEM,
            user_prompt=build_redline_prompt(
                issues_block=_render_issues(issues),
                clause_block=clause.full_text,
                issue_count=len(issues),
            ),
            schema_name="redline_draft",
            schema=REDLINE_SCHEMA,
            temperature=0.2,  # a little room to phrase naturally, not to invent terms
        )
    except LLMError as exc:
        logger.warning("Redline drafting failed for clause %s: %s", clause.number, exc)
        return "", ""

    return (
        str(response.get("proposed_redline", "")).strip(),
        str(response.get("change_summary", "")).strip(),
    )


def _render_issues(issues: list[tuple[Rule, str]]) -> str:
    blocks = []

    for index, (rule, problem) in enumerate(issues, start=1):
        block = (
            f"{index}. {rule.title}\n"
            f"   Rule: {rule.text}\n"
            f"   Why it matters: {rule.rationale}\n"
            f"   How this clause fails it: {problem}"
        )
        if rule.redline_guidance:
            block += f"\n   House position: {rule.redline_guidance}"
        blocks.append(block)

    return "\n\n".join(blocks)
