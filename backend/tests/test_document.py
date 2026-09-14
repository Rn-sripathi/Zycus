"""Reading uploaded contracts.

The risk here is silent: a file parses "fine", produces text, and the segmenter
then finds zero clauses because the numbering ended up mid-line. Every test below
asserts on clauses found, not on characters extracted.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from app.tools.document import (
    UnreadableDocument,
    UnsupportedDocument,
    extract_text,
    normalise,
)
from app.tools.segmenter import segment_clauses

SAMPLE = (
    Path(__file__).resolve().parents[1] / "app" / "data" / "sample_contract.txt"
).read_text(encoding="utf-8")


def _docx_bytes(text: str) -> bytes:
    import docx

    document = docx.Document()
    for block in [b.strip() for b in text.split("\n\n") if b.strip()]:
        document.add_paragraph(block)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _pdf_bytes(text: str) -> bytes:
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=LETTER)
    styles = getSampleStyleSheet()
    flow = []
    for block in [b.strip() for b in text.split("\n\n") if b.strip()]:
        flow.append(Paragraph(block.replace("&", "&amp;"), styles["Normal"]))
        flow.append(Spacer(1, 10))
    doc.build(flow)
    return buffer.getvalue()


class TestPlainText:
    def test_reads_utf8(self):
        text = extract_text("contract.txt", SAMPLE.encode("utf-8"))
        assert len(segment_clauses(text)) == 8

    def test_reads_utf8_with_bom(self):
        text = extract_text("contract.txt", SAMPLE.encode("utf-8-sig"))
        assert len(segment_clauses(text)) == 8
        assert not text.startswith("﻿")

    def test_reads_windows_encoding(self):
        text = extract_text("contract.txt", "1. Term. Fee is 50€.".encode("cp1252"))
        assert "50" in text


class TestWordDocuments:
    def test_finds_every_clause(self):
        text = extract_text("contract.docx", _docx_bytes(SAMPLE))
        assert [c.number for c in segment_clauses(text)] == [1, 2, 3, 4, 5, 6, 7, 8]

    def test_reads_clauses_held_in_tables(self):
        import docx

        document = docx.Document()
        table = document.add_table(rows=1, cols=2)
        table.rows[0].cells[0].text = "1."
        table.rows[0].cells[1].text = "Term. Either party may terminate on 7 days' notice."
        buffer = io.BytesIO()
        document.save(buffer)

        text = extract_text("tabular.docx", buffer.getvalue())
        assert "terminate" in text


class TestPdf:
    def test_finds_every_clause_despite_wrapping(self):
        """PDF extraction returns wrapped lines, so clause numbers land mid-line
        unless normalisation puts them back at the start of one."""
        text = extract_text("contract.pdf", _pdf_bytes(SAMPLE))
        assert [c.number for c in segment_clauses(text)] == [1, 2, 3, 4, 5, 6, 7, 8]

    def test_numbers_needed_by_the_gate_survive(self):
        text = extract_text("contract.pdf", _pdf_bytes(SAMPLE))
        clause_one = next(c for c in segment_clauses(text) if c.number == 1)
        assert "10 days" in clause_one.body
        assert "7 days" in clause_one.body
        assert "THREE (3)" in text


class TestNormalisation:
    def test_splits_clause_numbers_off_the_previous_sentence(self):
        run_on = "...upon 7 days' written notice. 2. Fees and Payment. Customer shall pay."
        assert len(segment_clauses(normalise(run_on))) == 1  # clause 2 now starts a line

    def test_rejoins_words_hyphenated_across_lines(self):
        assert "indemnification" in normalise("indemn-\nification obligations")

    def test_does_not_split_decimals_or_money(self):
        text = normalise("Interest accrues at 2.5% per month. Fees are 1,000.00 USD.")
        assert "2.5%" in text
        assert "1,000.00" in text


class TestRejections:
    def test_unsupported_extension(self):
        with pytest.raises(UnsupportedDocument):
            extract_text("contract.xlsx", b"whatever")

    def test_empty_file(self):
        with pytest.raises(UnreadableDocument):
            extract_text("contract.txt", b"")

    def test_oversized_file(self):
        with pytest.raises(UnreadableDocument, match="larger than"):
            extract_text("contract.txt", b"x" * (11 * 1024 * 1024))

    def test_corrupt_pdf(self):
        with pytest.raises(UnreadableDocument):
            extract_text("contract.pdf", b"%PDF-1.4 this is not really a pdf")

    def test_file_with_no_readable_text(self):
        with pytest.raises(UnreadableDocument):
            extract_text("contract.txt", b"   \n\n   \t  ")
