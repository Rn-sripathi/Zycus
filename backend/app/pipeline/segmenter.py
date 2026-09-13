"""Pipeline step 1: split raw contract text into numbered clauses.

Deterministic -- no model involved. Runs in microseconds and is fully unit-tested,
which means a segmentation bug can never be mistaken for a model failure.
"""

from __future__ import annotations

import re

from app.domain.models import Clause

# Matches a clause header at the start of a line: "1. Term and Termination."
# The heading is the short title before the first period; everything after is body.
_CLAUSE_START = re.compile(r"^[ \t]*(\d{1,2})[.)]\s+", re.MULTILINE)

# Splits "Term and Termination. This Agreement shall..." into heading + body.
# Requires the heading to be reasonably short so a long opening sentence is not
# mistaken for a title.
_HEADING = re.compile(r"^(?P<heading>[^.]{1,80}?)\.\s+(?P<body>.*)$", re.DOTALL)


def segment_clauses(contract_text: str) -> list[Clause]:
    """Return the numbered clauses found in ``contract_text``.

    Any preamble before clause 1 (title block, recitals) is ignored: it carries no
    obligations to review.
    """
    if not contract_text or not contract_text.strip():
        return []

    matches = list(_CLAUSE_START.finditer(contract_text))
    if not matches:
        return []

    clauses: list[Clause] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(contract_text)
        raw = contract_text[start:end].strip()
        if not raw:
            continue

        number = int(match.group(1))
        heading, body = _split_heading(raw)
        clauses.append(Clause(number=number, heading=heading, body=body))

    return clauses


def _split_heading(raw: str) -> tuple[str, str]:
    """Split a clause body into (heading, body).

    Falls back to an empty heading when the clause does not use the
    "Title. Sentence..." convention, rather than guessing.
    """
    collapsed = " ".join(raw.split())
    match = _HEADING.match(collapsed)
    if not match:
        return "", collapsed

    heading = match.group("heading").strip()
    body = match.group("body").strip()

    # A "heading" containing sentence-like filler is probably not a heading.
    if len(heading.split()) > 8:
        return "", collapsed

    return heading, body
