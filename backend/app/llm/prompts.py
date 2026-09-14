"""Prompt templates and response schemas for the three model-backed steps.

Kept separate from control flow so prompt iteration produces readable diffs.
"""

from __future__ import annotations

from typing import Any

from app.domain.playbook import VALID_RULE_IDS

# ---------------------------------------------------------------------------
# Step 2: rule matching
# ---------------------------------------------------------------------------

RULE_MATCHER_SYSTEM = """\
You are a contract analyst for Zycus, a procurement software company. You are given \
the clauses of a counterparty-proposed contract and a playbook of internal rules.

Your only job is to decide which playbook rules are RELEVANT to each clause -- that is, \
which rules govern the subject matter the clause deals with. Do not decide whether the \
clause complies; another step does that.

Guidance:
- A clause can be relevant to more than one rule. For example a "Term and Termination" \
clause that covers both auto-renewal notice and termination for convenience is relevant \
to both of those rules.
- A clause can be relevant to no rules at all. Boilerplate such as entire-agreement, \
notices, or a confidentiality standard that the playbook does not cover should return an \
empty list. Do not force a match.
- Match on subject matter, not on whether the wording looks favourable or unfavourable.\
"""

def build_rule_matcher_schema(rule_ids: tuple[str, ...] = VALID_RULE_IDS) -> dict[str, Any]:
    """Constrain the model to the ids of the playbook actually in use.

    Built per call rather than once at import, because the playbook can be
    replaced at request time and a stale enum would let the model return ids that
    no longer exist.
    """
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["matches"],
        "properties": {
            "matches": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["clause_number", "rule_ids"],
                    "properties": {
                        "clause_number": {"type": "integer"},
                        "rule_ids": {
                            "type": "array",
                            "items": {"type": "string", "enum": list(rule_ids)},
                        },
                    },
                },
            }
        },
    }


def build_rule_matcher_prompt(clauses_block: str, rules_block: str) -> str:
    return (
        f"PLAYBOOK RULES:\n{rules_block}\n\n"
        f"CONTRACT CLAUSES:\n{clauses_block}\n\n"
        "For every clause listed above, return the ids of the playbook rules that govern "
        "its subject matter. Return an empty list for clauses no rule covers."
    )


# ---------------------------------------------------------------------------
# Step 4: compliance checking
# ---------------------------------------------------------------------------

COMPLIANCE_SYSTEM = """\
You are a contract analyst for Zycus, a procurement software company, reviewing a \
counterparty-proposed contract against Zycus's internal playbook. Zycus is the CUSTOMER \
in this agreement; the counterparty is the VENDOR. Judge every clause from Zycus's side.

You are given one clause and one playbook rule. Decide whether the clause violates that \
rule, and quote the exact words that drive your conclusion.

Report your confidence honestly -- this number decides whether a human reviews the finding:
- 0.9-1.0: the clause states the violating (or complying) position explicitly and there is \
only one reasonable reading.
- 0.7-0.89: strongly implied, but a lawyer might phrase the conclusion differently.
- below 0.7: the clause is vague, hedged, defers to outside standards such as \
"commercially reasonable" or "customary practice", or could plausibly be read either way.

Never inflate confidence to seem decisive. A clause that genuinely cannot be judged from \
its own words must receive a low score so a human sees it. If you cannot find words in the \
clause that support your conclusion, that is itself a reason for low confidence, and \
evidence_quote must be left empty rather than invented.\
"""

COMPLIANCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["violation", "confidence", "evidence_quote", "reasoning"],
    "properties": {
        "violation": {
            "type": "boolean",
            "description": "True if the clause fails the rule, judged from Zycus's side.",
        },
        "confidence": {
            "type": "number",
            "description": "0.0-1.0, how certain you are of the verdict.",
        },
        "evidence_quote": {
            "type": "string",
            "description": "Exact words from the clause supporting the verdict; empty if none.",
        },
        "reasoning": {
            "type": "string",
            "description": "One or two sentences, plain English, no legalese.",
        },
    },
}


def build_compliance_prompt(rule_block: str, clause_block: str) -> str:
    return (
        f"PLAYBOOK RULE:\n{rule_block}\n\n"
        f"CLAUSE UNDER REVIEW:\n{clause_block}\n\n"
        "Does this clause violate the rule, judged from Zycus's position as customer?"
    )


# ---------------------------------------------------------------------------
# Step 5: redline drafting
# ---------------------------------------------------------------------------

REDLINE_SYSTEM = """\
You are a contract attorney drafting redlines for Zycus, the customer in this agreement.

Rewrite the clause you are given so that it complies with the playbook rules listed, and \
return the replacement text only.

Requirements:
- Produce actual clause language that could be pasted into the contract. Never write \
commentary such as "consider revising" or "this should be negotiated".
- A clause may breach SEVERAL rules at once. Your replacement must fix EVERY issue listed, \
in one piece of text. Fixing one and leaving another unchanged is a serious error: the \
reviewer pastes your text into the contract, so anything you leave unfixed ships.
- Change what the rules require and leave the rest of the clause intact. Keep the original \
numbering, defined terms and drafting style.
- Where a rule sets a threshold, state the number explicitly in the replacement text.
- Keep it proportionate: this is a redline, not a rewrite of the whole agreement.\
"""

REDLINE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["proposed_redline", "change_summary"],
    "properties": {
        "proposed_redline": {
            "type": "string",
            "description": "The full replacement clause text.",
        },
        "change_summary": {
            "type": "string",
            "description": "One short sentence naming what changed and why.",
        },
    },
}


def build_redline_prompt(issues_block: str, clause_block: str, issue_count: int) -> str:
    instruction = (
        "Draft the replacement clause."
        if issue_count == 1
        else (
            f"This clause breaches {issue_count} rules. Draft ONE replacement clause that "
            "fixes all of them together."
        )
    )
    return (
        f"ISSUES TO FIX IN THIS CLAUSE:\n{issues_block}\n\n"
        f"CLAUSE AS PROPOSED BY THE VENDOR:\n{clause_block}\n\n"
        f"{instruction}"
    )
