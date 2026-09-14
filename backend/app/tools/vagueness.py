"""Deterministic vagueness detection.

Asking a model how confident it is turns out to be close to useless: on a clause
whose operative wording is "a commercially reasonable amount", gpt-4o-mini reports
0.8, and on "such jurisdiction as the parties may mutually determine" it reports
0.9 *and* concludes there is no violation. Self-reported confidence clusters high
regardless of how little the clause actually commits to.

So confidence is not left to the model in either direction. Arithmetic overrides it
upward (numeric_gate); this module overrides it downward. When a clause defers to an
outside standard instead of stating a position, no verdict about it can be read off
the text, so the finding is routed to a human whatever the model claims.

Over-flagging here is the safe error: the cost is a reviewer glancing at a clause,
against the cost of silently approving one nobody read.
"""

from __future__ import annotations

import re

# Phrases that defer the substance elsewhere rather than stating a position.
_HEDGE_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"commercially reasonable", "commercially reasonable"),
    (
        r"reasonabl[ey]\s+(?:prior\s+)?(?:written\s+)?"
        r"(?:notice|period|time|amount|effort|efforts|care|manner)",
        "an undefined reasonableness standard",
    ),
    (r"reasonably\s+(?:necessary|related|appropriate|determined)", "a reasonableness standard"),
    (r"to be determined", "terms left to be determined"),
    (r"as\s+(?:may\s+be\s+)?appropriate", "an undefined appropriateness standard"),
    (r"mutually\s+(?:determine|agree|acceptable|appropriate)", "terms left to later agreement"),
    (r"as the parties may", "terms left to later agreement"),
    (r"customary", "an appeal to customary practice"),
    (r"course of dealing", "an appeal to past course of dealing"),
    (r"industry\s+(?:practice|standard|allocation)", "an appeal to industry practice"),
    (r"respective interests", "an appeal to the parties' respective interests"),
    (r"to the extent consistent", "an open-ended consistency qualifier"),
    (r"from time to time", "an open-ended timing qualifier"),
    (r"best efforts", "an efforts standard rather than an obligation"),
)

_COMPILED = tuple((re.compile(pattern, re.IGNORECASE), label) for pattern, label in _HEDGE_PATTERNS)


def detect_hedges(*texts: str) -> list[str]:
    """Return the distinct hedge descriptions found across ``texts``.

    Accepts several strings so the clause body and the quote the model relied on can
    be checked together: a hedge inside the quoted evidence is the strongest signal
    that the verdict rests on wording that does not actually commit to anything.
    """
    found: list[str] = []

    for text in texts:
        if not text:
            continue
        for pattern, label in _COMPILED:
            if pattern.search(text) and label not in found:
                found.append(label)

    return found
