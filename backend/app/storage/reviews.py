"""Reading and writing reviews.

Explicit SQL rather than an ORM: the queries are few and the shapes are simple,
so a mapping layer would cost more than it saves. Domain objects go in, domain
objects come out, and nothing above this module knows Postgres exists.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime

from app.domain.models import (
    EvidenceSource,
    Finding,
    GateResult,
    NumericEvidence,
    ReviewResult,
    ReviewSummary,
    Severity,
    Tier,
    Unit,
    Verdict,
)
from app.storage import db

logger = logging.getLogger(__name__)

_INSERT_REVIEW = """
INSERT INTO reviews (
    id, label, contract_text, model,
    clauses_reviewed, deviations, serious, minor,
    auto_suggested, needs_review, uncovered, elapsed_seconds
) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
RETURNING created_at
"""

_INSERT_FINDING = """
INSERT INTO findings (
    review_id, position, clause_number, clause_heading, rule_id, rule_title,
    verdict, tier, severity, auto_suggest, needs_review, source,
    original_text, evidence_quote, explanation, proposed_redline, change_summary,
    redline_addresses, review_reasons, numeric_evidence
) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,
          $18::jsonb,$19::jsonb,$20::jsonb)
"""

_LIST_REVIEWS = """
SELECT id, created_at, label, model, clauses_reviewed, deviations, serious,
       minor, auto_suggested, needs_review, uncovered, elapsed_seconds
FROM reviews
ORDER BY created_at DESC
LIMIT $1 OFFSET $2
"""

_GET_REVIEW = "SELECT * FROM reviews WHERE id = $1"

_GET_FINDINGS = "SELECT * FROM findings WHERE review_id = $1 ORDER BY position"


@dataclass(frozen=True)
class StoredReview:
    """A row from the history list. Summary only, no findings."""

    id: uuid.UUID
    created_at: datetime
    label: str
    model: str
    summary: ReviewSummary


async def save_review(
    result: ReviewResult,
    contract_text: str,
    *,
    label: str = "",
    model: str = "",
) -> uuid.UUID | None:
    """Persist a completed review. Returns None when persistence is disabled.

    Never raises: a storage outage must not lose the reviewer the findings that
    are already on their screen.
    """
    pool = db.get_pool()
    if pool is None:
        return None

    review_id = uuid.uuid4()
    s = result.summary

    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.fetchval(
                    _INSERT_REVIEW,
                    review_id, label, contract_text, model,
                    s.clauses_reviewed, s.deviations, s.serious, s.minor,
                    s.auto_suggested, s.needs_review,
                    s.clauses_without_applicable_rule, s.elapsed_seconds,
                )
                await connection.executemany(
                    _INSERT_FINDING,
                    [_finding_row(review_id, i, f) for i, f in enumerate(result.findings)],
                )
    except Exception:  # noqa: BLE001 - persistence is best-effort by design
        logger.exception("Could not persist review; returning results anyway")
        return None

    return review_id


async def list_reviews(limit: int = 25, offset: int = 0) -> list[StoredReview]:
    pool = db.get_pool()
    if pool is None:
        return []

    rows = await pool.fetch(_LIST_REVIEWS, limit, offset)
    return [
        StoredReview(
            id=row["id"],
            created_at=row["created_at"],
            label=row["label"],
            model=row["model"],
            summary=ReviewSummary(
                clauses_reviewed=row["clauses_reviewed"],
                deviations=row["deviations"],
                serious=row["serious"],
                minor=row["minor"],
                auto_suggested=row["auto_suggested"],
                needs_review=row["needs_review"],
                clauses_without_applicable_rule=row["uncovered"],
                elapsed_seconds=row["elapsed_seconds"],
            ),
        )
        for row in rows
    ]


async def get_review(review_id: uuid.UUID) -> tuple[ReviewResult, str] | None:
    """Return ``(result, contract_text)`` for a stored review, or None."""
    pool = db.get_pool()
    if pool is None:
        return None

    async with pool.acquire() as connection:
        review = await connection.fetchrow(_GET_REVIEW, review_id)
        if review is None:
            return None
        rows = await connection.fetch(_GET_FINDINGS, review_id)

    summary = ReviewSummary(
        clauses_reviewed=review["clauses_reviewed"],
        deviations=review["deviations"],
        serious=review["serious"],
        minor=review["minor"],
        auto_suggested=review["auto_suggested"],
        needs_review=review["needs_review"],
        clauses_without_applicable_rule=review["uncovered"],
        elapsed_seconds=review["elapsed_seconds"],
    )
    findings = [_finding_from_row(row) for row in rows]
    return ReviewResult(findings=findings, summary=summary), review["contract_text"]


async def delete_review(review_id: uuid.UUID) -> bool:
    pool = db.get_pool()
    if pool is None:
        return False
    status = await pool.execute("DELETE FROM reviews WHERE id = $1", review_id)
    return status.endswith("1")


def _finding_row(review_id: uuid.UUID, position: int, f: Finding) -> tuple:
    numeric = None
    if f.numeric is not None:
        numeric = json.dumps(
            {
                "result": f.numeric.result.value,
                "found_value": f.numeric.found_value,
                "threshold": f.numeric.threshold,
                "unit": f.numeric.unit.value if f.numeric.unit else None,
                "excerpt": f.numeric.excerpt,
                "explanation": f.numeric.explanation,
            }
        )

    return (
        review_id, position, f.clause_number, f.clause_heading, f.rule_id, f.rule_title,
        f.verdict.value,
        f.tier.value if f.tier else None,
        f.severity.value if f.severity else None,
        f.auto_suggest, f.needs_review,
        f.source.value if f.source else None,
        f.original_text, f.evidence_quote, f.explanation, f.proposed_redline,
        f.change_summary,
        json.dumps(f.redline_addresses), json.dumps(f.review_reasons), numeric,
    )


def _finding_from_row(row) -> Finding:
    numeric = None
    raw = row["numeric_evidence"]
    if raw:
        data = json.loads(raw) if isinstance(raw, str) else raw
        numeric = NumericEvidence(
            result=GateResult(data["result"]),
            found_value=data.get("found_value"),
            threshold=data.get("threshold"),
            unit=Unit(data["unit"]) if data.get("unit") else None,
            excerpt=data.get("excerpt", ""),
            explanation=data.get("explanation", ""),
        )

    return Finding(
        clause_number=row["clause_number"],
        clause_heading=row["clause_heading"],
        rule_id=row["rule_id"],
        rule_title=row["rule_title"],
        verdict=Verdict(row["verdict"]),
        original_text=row["original_text"],
        tier=Tier(row["tier"]) if row["tier"] else None,
        severity=Severity(row["severity"]) if row["severity"] else None,
        auto_suggest=row["auto_suggest"],
        needs_review=row["needs_review"],
        source=EvidenceSource(row["source"]) if row["source"] else None,
        evidence_quote=row["evidence_quote"],
        explanation=row["explanation"],
        proposed_redline=row["proposed_redline"],
        change_summary=row["change_summary"],
        redline_addresses=_as_list(row["redline_addresses"]),
        review_reasons=_as_list(row["review_reasons"]),
        numeric=numeric,
    )


def _as_list(value) -> list[str]:
    if not value:
        return []
    return json.loads(value) if isinstance(value, str) else list(value)
