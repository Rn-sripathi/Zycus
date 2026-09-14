"""Persistence round trip.

Needs a real DATABASE_URL and is skipped without one, so the offline suite stays
offline. Writes and deletes its own rows; it does not touch anything else.

    DATABASE_URL=postgresql://... python -m pytest tests/test_storage.py -v
"""

from __future__ import annotations

import asyncio

import pytest

from app.config import get_settings
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
from app.storage import reviews as store

pytestmark = pytest.mark.skipif(
    not get_settings().persistence_enabled,
    reason="DATABASE_URL not configured; storage tests skipped",
)

CONTRACT = "1. Term and Termination. Either party may terminate upon 7 days' notice."


def _sample_result() -> ReviewResult:
    """One finding of each shape that has to survive the round trip."""
    return ReviewResult(
        findings=[
            Finding(
                clause_number=1,
                clause_heading="Term and Termination",
                rule_id="termination_notice",
                rule_title="Termination for convenience notice",
                verdict=Verdict.DEVIATION,
                original_text=CONTRACT,
                tier=Tier.HIGH,
                severity=Severity.MINOR,
                auto_suggest=True,
                needs_review=False,
                source=EvidenceSource.DETERMINISTIC,
                evidence_quote="upon 7 days' notice",
                explanation="Found 7 days; playbook requires at least 30 days.",
                proposed_redline="1. Term and Termination. ... thirty (30) days' notice.",
                change_summary="Extended notice to 30 days.",
                redline_addresses=["Auto-renewal notice", "Termination notice"],
                numeric=NumericEvidence(
                    result=GateResult.VERIFIED_VIOLATION,
                    found_value=7,
                    threshold=30,
                    unit=Unit.DAYS,
                    excerpt="upon 7 days' notice",
                    explanation="7 < 30",
                ),
            ),
            Finding(
                clause_number=2,
                clause_heading="Data Rights",
                rule_id="data_ownership",
                rule_title="Data ownership",
                verdict=Verdict.COMPLIANT,
                original_text="2. Data Rights. Handled reasonably.",
                tier=Tier.LOW,
                severity=None,
                auto_suggest=False,
                needs_review=True,
                source=EvidenceSource.LLM,
                review_reasons=["The clause relies on a reasonableness standard."],
            ),
            Finding(
                clause_number=3,
                clause_heading="General",
                rule_id=None,
                rule_title=None,
                verdict=Verdict.NO_APPLICABLE_RULE,
                original_text="3. General. Entire agreement.",
            ),
        ],
        summary=ReviewSummary(
            clauses_reviewed=3,
            deviations=1,
            serious=0,
            minor=1,
            auto_suggested=1,
            needs_review=1,
            clauses_without_applicable_rule=1,
            elapsed_seconds=1.23,
        ),
    )


@pytest.fixture(scope="module")
def run():
    """One event loop for the whole module.

    asyncpg binds its pool to the loop that created it, so a fresh asyncio.run()
    per test would leave every call talking to a closed loop.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(db.connect())
    try:
        yield loop.run_until_complete
    finally:
        loop.run_until_complete(db.disconnect())
        loop.close()
        asyncio.set_event_loop(None)


@pytest.fixture
def saved(run):
    review_id = run(
        store.save_review(_sample_result(), CONTRACT, label="pytest", model="test-model")
    )
    yield review_id
    run(store.delete_review(review_id))


class TestRoundTrip:
    def test_save_returns_an_id(self, saved):
        assert saved is not None

    def test_findings_survive_unchanged(self, run, saved):
        result, contract, _ = run(store.get_review(saved))
        assert contract == CONTRACT
        assert len(result.findings) == 3

        original = _sample_result().findings
        for before, after in zip(original, result.findings, strict=True):
            assert after.clause_number == before.clause_number
            assert after.verdict is before.verdict
            assert after.tier is before.tier
            assert after.severity is before.severity
            assert after.auto_suggest == before.auto_suggest
            assert after.needs_review == before.needs_review
            assert after.source is before.source
            assert after.proposed_redline == before.proposed_redline
            assert after.redline_addresses == before.redline_addresses
            assert after.review_reasons == before.review_reasons

    def test_numeric_evidence_survives(self, run, saved):
        result, _, _ = run(store.get_review(saved))
        numeric = result.findings[0].numeric
        assert numeric is not None
        assert numeric.found_value == 7
        assert numeric.threshold == 30
        assert numeric.unit is Unit.DAYS
        assert numeric.result is GateResult.VERIFIED_VIOLATION

    def test_finding_order_is_preserved(self, run, saved):
        result, _, _ = run(store.get_review(saved))
        assert [f.clause_number for f in result.findings] == [1, 2, 3]

    def test_summary_survives(self, run, saved):
        result, _, _ = run(store.get_review(saved))
        assert result.summary.deviations == 1
        assert result.summary.needs_review == 1
        assert result.summary.clauses_without_applicable_rule == 1


class TestHistory:
    def test_saved_review_appears_in_the_list(self, run, saved):
        listed = run(store.list_reviews(limit=50))
        assert any(item.id == saved for item in listed)

    def test_list_carries_the_summary_without_findings(self, run, saved):
        item = next(i for i in run(store.list_reviews(limit=50)) if i.id == saved)
        assert item.label == "pytest"
        assert item.model == "test-model"
        assert item.summary.clauses_reviewed == 3


class TestDeletion:
    def test_delete_removes_the_review_and_its_findings(self, run):
        review_id = run(store.save_review(_sample_result(), CONTRACT, label="temp"))
        assert run(store.delete_review(review_id)) is True
        assert run(store.get_review(review_id)) is None

    def test_deleting_an_unknown_id_is_not_an_error(self, run):
        import uuid

        assert run(store.delete_review(uuid.uuid4())) is False


class TestMissingReview:
    def test_unknown_id_returns_none(self, run):
        import uuid

        assert run(store.get_review(uuid.uuid4())) is None
