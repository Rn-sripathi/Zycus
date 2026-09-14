"""Tests for clause segmentation, run against the real sample contract file."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.tools.segmenter import segment_clauses

SAMPLE = (Path(__file__).resolve().parents[1] / "app" / "data" / "sample_contract.txt").read_text(
    encoding="utf-8"
)


@pytest.fixture(scope="module")
def clauses():
    return segment_clauses(SAMPLE)


def test_finds_all_eight_clauses(clauses):
    assert [c.number for c in clauses] == [1, 2, 3, 4, 5, 6, 7, 8]


def test_extracts_headings(clauses):
    headings = {c.number: c.heading for c in clauses}
    assert headings[1] == "Term and Termination"
    assert headings[3] == "Limitation of Liability"
    assert headings[8] == "General"


def test_ignores_the_preamble(clauses):
    # The title block and "entered into between..." carry no obligations.
    assert "VENDOR SERVICES AGREEMENT" not in clauses[0].full_text


def test_all_caps_clause_is_segmented_normally(clauses):
    clause_3 = next(c for c in clauses if c.number == 3)
    assert "THREE (3)" in clause_3.body
    assert clause_3.heading == "Limitation of Liability"


def test_clause_one_keeps_both_notice_periods(clauses):
    clause_1 = next(c for c in clauses if c.number == 1)
    assert "10 days" in clause_1.body
    assert "7 days" in clause_1.body


def test_empty_input_returns_no_clauses():
    assert segment_clauses("") == []
    assert segment_clauses("   \n  ") == []


def test_text_without_numbered_clauses_returns_nothing():
    assert segment_clauses("This agreement has no numbered clauses at all.") == []
