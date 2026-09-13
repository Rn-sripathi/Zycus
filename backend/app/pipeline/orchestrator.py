"""Runs the six pipeline steps and assembles the review.

Reads top to bottom in the same order as the architecture diagram:

    1 segment  ->  2 match rules  ->  3 numeric gate  ->  4 compliance check
                ->  5 draft redlines  ->  6 classify

Steps 4 and 5 fan out with asyncio.gather. Done sequentially, a review of the
sample contract would mean roughly fifteen round trips one after another; run
concurrently it is two waves.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

from app.config import get_settings
from app.domain.models import (
    Clause,
    Finding,
    GateResult,
    LLMAssessment,
    NumericEvidence,
    ReviewResult,
    ReviewSummary,
    Rule,
    RuleType,
    Severity,
    Verdict,
)
from app.llm.client import LLMClient
from app.pipeline import compliance, redliner, rule_matcher
from app.pipeline.hitl import classify
from app.pipeline.numeric_gate import evaluate_numeric_rule
from app.pipeline.segmenter import segment_clauses
from app.pipeline.vagueness import detect_hedges

logger = logging.getLogger(__name__)


@dataclass
class _Pair:
    """One clause checked against one rule, carried through the pipeline."""

    clause: Clause
    rule: Rule
    numeric: NumericEvidence | None = None
    assessment: LLMAssessment | None = None


async def review_contract(contract_text: str, client: LLMClient) -> ReviewResult:
    started = time.perf_counter()
    settings = get_settings()

    # Step 1 -- deterministic.
    clauses = segment_clauses(contract_text)
    if not clauses:
        return ReviewResult(findings=[], summary=ReviewSummary())

    # Step 2 -- one batched model call.
    matches = await rule_matcher.match_rules(clauses, client)

    # Step 3 -- deterministic arithmetic wherever a rule has a threshold.
    pairs: list[_Pair] = []
    for clause in clauses:
        for rule in matches.get(clause.number, []):
            pair = _Pair(clause=clause, rule=rule)
            if rule.rule_type is RuleType.NUMERIC:
                pair.numeric = evaluate_numeric_rule(clause, rule)
            pairs.append(pair)

    # Step 4 -- model judgment only where arithmetic could not settle it.
    undecided = [pair for pair in pairs if _needs_model_judgment(pair)]
    if undecided:
        assessments = await asyncio.gather(
            *(compliance.check_compliance(p.clause, p.rule, client) for p in undecided),
            return_exceptions=False,
        )
        for pair, assessment in zip(undecided, assessments, strict=True):
            pair.assessment = assessment

    # Step 6 -- classify first, so drafting only runs for real deviations.
    # Vagueness is checked in Python: the model reports high confidence on clauses
    # that state nothing, so its self-assessment cannot be the only brake.
    decisions = [
        classify(
            pair.rule,
            numeric=pair.numeric,
            assessment=pair.assessment,
            hedges=(
                detect_hedges(pair.clause.full_text, pair.assessment.evidence_quote)
                if pair.assessment is not None
                else []
            ),
            confidence_threshold=settings.confidence_threshold,
        )
        for pair in pairs
    ]

    # Step 5 -- draft replacement language, one call per CLAUSE rather than per rule.
    # A clause breaching two rules needs a single replacement that fixes both; drafting
    # them separately yields two texts that each undo the other's fix.
    deviating_by_clause: dict[int, list[_Pair]] = {}
    for pair, decision in zip(pairs, decisions, strict=True):
        if decision.verdict is Verdict.DEVIATION:
            deviating_by_clause.setdefault(pair.clause.number, []).append(pair)

    drafts: dict[int, tuple[str, str]] = {}
    if deviating_by_clause:
        clause_numbers = list(deviating_by_clause)
        redlines = await asyncio.gather(
            *(
                redliner.draft_redline(
                    deviating_by_clause[number][0].clause,
                    [(p.rule, _describe_problem(p)) for p in deviating_by_clause[number]],
                    client,
                )
                for number in clause_numbers
            )
        )
        drafts = dict(zip(clause_numbers, redlines, strict=True))

    findings = _build_findings(clauses, pairs, decisions, deviating_by_clause, drafts)
    summary = _summarise(clauses, findings, time.perf_counter() - started)
    return ReviewResult(findings=findings, summary=summary)


def _needs_model_judgment(pair: _Pair) -> bool:
    """Qualitative rules always; numeric rules only when no number could be read."""
    if pair.rule.rule_type is not RuleType.NUMERIC:
        return True
    return pair.numeric is None or pair.numeric.result is GateResult.NOT_EXTRACTABLE


def _describe_problem(pair: _Pair) -> str:
    if pair.numeric is not None and pair.numeric.result is GateResult.VERIFIED_VIOLATION:
        return pair.numeric.explanation
    if pair.assessment is not None:
        return pair.assessment.reasoning
    return f"The clause does not meet the rule: {pair.rule.text}"


def _build_findings(
    clauses: list[Clause],
    pairs: list[_Pair],
    decisions: list,
    deviating_by_clause: dict[int, list[_Pair]],
    drafts: dict[int, tuple[str, str]],
) -> list[Finding]:
    findings: list[Finding] = []

    by_clause: dict[int, list[tuple[_Pair, object]]] = {}
    for pair, decision in zip(pairs, decisions, strict=True):
        by_clause.setdefault(pair.clause.number, []).append((pair, decision))

    for clause in clauses:
        entries = by_clause.get(clause.number, [])

        # A clause no rule governs is reported as such, rather than as a silent pass.
        if not entries:
            findings.append(
                Finding(
                    clause_number=clause.number,
                    clause_heading=clause.heading,
                    rule_id=None,
                    rule_title=None,
                    verdict=Verdict.NO_APPLICABLE_RULE,
                    original_text=clause.full_text,
                    explanation=(
                        "No playbook rule covers the subject matter of this clause, so it "
                        "was not assessed. Worth a glance if the playbook is incomplete."
                    ),
                )
            )
            continue

        # One consolidated replacement per clause, shared by that clause's findings.
        clause_deviations = deviating_by_clause.get(clause.number, [])
        addressed = [p.rule.title for p in clause_deviations]

        for pair, decision in entries:
            is_deviation = decision.verdict is Verdict.DEVIATION
            redline, change_summary = drafts.get(clause.number, ("", "")) if is_deviation else ("", "")
            findings.append(
                Finding(
                    clause_number=clause.number,
                    clause_heading=clause.heading,
                    rule_id=pair.rule.id,
                    rule_title=pair.rule.title,
                    verdict=decision.verdict,
                    original_text=clause.full_text,
                    tier=decision.tier,
                    severity=decision.severity,
                    auto_suggest=decision.auto_suggest,
                    needs_review=decision.needs_review,
                    source=decision.source,
                    evidence_quote=_evidence_quote(pair),
                    explanation=_explanation(pair),
                    proposed_redline=redline,
                    change_summary=change_summary,
                    redline_addresses=addressed if is_deviation and len(addressed) > 1 else [],
                    numeric=pair.numeric,
                    review_reasons=list(decision.review_reasons),
                )
            )

    findings.sort(key=_finding_sort_key)
    return findings


def _evidence_quote(pair: _Pair) -> str:
    if pair.numeric is not None and pair.numeric.excerpt:
        return pair.numeric.excerpt
    if pair.assessment is not None:
        return pair.assessment.evidence_quote
    return ""


def _explanation(pair: _Pair) -> str:
    if pair.numeric is not None and pair.numeric.result is not GateResult.NOT_EXTRACTABLE:
        return pair.numeric.explanation
    if pair.assessment is not None:
        return pair.assessment.reasoning
    return ""


def _finding_sort_key(finding: Finding) -> tuple[int, int, int]:
    """Most actionable first: deviations, serious before minor, then by clause."""
    verdict_rank = {
        Verdict.DEVIATION: 0,
        Verdict.COMPLIANT: 1,
        Verdict.NO_APPLICABLE_RULE: 2,
    }[finding.verdict]

    severity_rank = 0 if finding.severity is Severity.SERIOUS else 1
    return (verdict_rank, severity_rank, finding.clause_number)


def _summarise(
    clauses: list[Clause], findings: list[Finding], elapsed: float
) -> ReviewSummary:
    deviations = [f for f in findings if f.verdict is Verdict.DEVIATION]
    return ReviewSummary(
        clauses_reviewed=len(clauses),
        deviations=len(deviations),
        serious=sum(1 for f in deviations if f.severity is Severity.SERIOUS),
        minor=sum(1 for f in deviations if f.severity is Severity.MINOR),
        auto_suggested=sum(1 for f in findings if f.auto_suggest),
        needs_review=sum(1 for f in findings if f.needs_review),
        clauses_without_applicable_rule=sum(
            1 for f in findings if f.verdict is Verdict.NO_APPLICABLE_RULE
        ),
        elapsed_seconds=round(elapsed, 2),
    )
