"""Pipeline step 2: decide which playbook rules govern which clauses.

Model-based rather than a keyword table, because the product has to work on a
contract the user pastes in, not only on the shipped sample. A keyword map would
match nothing the moment clause headings differ -- and fail silently, which is the
worst kind of failure in a review tool.

A keyword fallback is kept for the case where the model call itself errors, so a
transient outage degrades the result instead of emptying it.

The playbook is passed in rather than imported, so a caller can supply its own.
"""

from __future__ import annotations

import logging

from app.domain.models import Clause, Rule
from app.domain.playbook import PLAYBOOK
from app.llm.client import LLMClient, LLMError
from app.llm.prompts import (
    RULE_MATCHER_SYSTEM,
    build_rule_matcher_prompt,
    build_rule_matcher_schema,
)

logger = logging.getLogger(__name__)

ClauseRuleMap = dict[int, list[Rule]]


async def match_rules(
    clauses: list[Clause],
    client: LLMClient,
    rules: tuple[Rule, ...] = PLAYBOOK,
) -> ClauseRuleMap:
    """Map each clause number to the playbook rules that govern it."""
    if not clauses or not rules:
        return {clause.number: [] for clause in clauses}

    try:
        response = await client.complete_json(
            system_prompt=RULE_MATCHER_SYSTEM,
            user_prompt=build_rule_matcher_prompt(
                clauses_block=_render_clauses(clauses),
                rules_block=_render_rules(rules),
            ),
            schema_name="rule_matches",
            schema=build_rule_matcher_schema(tuple(rule.id for rule in rules)),
        )
    except LLMError as exc:
        logger.warning("Rule matcher failed (%s); falling back to keyword matching", exc)
        return keyword_match(clauses, rules)

    return _parse_matches(response, clauses, rules)


def keyword_match(
    clauses: list[Clause],
    rules: tuple[Rule, ...] = PLAYBOOK,
) -> ClauseRuleMap:
    """Deterministic fallback: match on the keywords declared in the playbook."""
    matches: ClauseRuleMap = {}

    for clause in clauses:
        haystack = clause.full_text.lower()
        matches[clause.number] = [
            rule for rule in rules if any(kw in haystack for kw in rule.keywords)
        ]

    return matches


def _parse_matches(
    response: dict,
    clauses: list[Clause],
    rules: tuple[Rule, ...],
) -> ClauseRuleMap:
    by_id = {rule.id: rule for rule in rules}
    valid_numbers = {clause.number for clause in clauses}
    matches: ClauseRuleMap = {clause.number: [] for clause in clauses}

    for entry in response.get("matches", []):
        number = entry.get("clause_number")
        if number not in valid_numbers:
            continue

        matched: list[Rule] = []
        for rule_id in entry.get("rule_ids", []):
            rule = by_id.get(rule_id)
            if rule is not None and rule not in matched:
                matched.append(rule)

        matches[number] = matched

    return matches


def _render_clauses(clauses: list[Clause]) -> str:
    return "\n\n".join(clause.full_text for clause in clauses)


def _render_rules(rules: tuple[Rule, ...]) -> str:
    return "\n".join(f"- {rule.id}: {rule.text}" for rule in rules)
