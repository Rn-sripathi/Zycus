# Zycus Redlining Agent

Reviews a counterparty-proposed contract against the Zycus standard playbook, proposes
specific replacement language for each deviation, and separates findings it can verify
from findings a human should judge.

Built for the Zycus Product Intern (AI PM track) take-home, Track B.

- **Live app:** _add your deployed URL here_
- **Slide deck:** [`docs/Zycus_Redlining_Agent_Deck.pptx`](docs/Zycus_Redlining_Agent_Deck.pptx)
  (6 slides) — also as [`docs/deck.html`](docs/deck.html) and published at
  https://claude.ai/code/artifact/c8ecd3f4-7e8e-4c6a-b09e-a1e8849e58e5
- **Written version:** [`docs/Zycus_Redlining_Agent_Writeup.docx`](docs/Zycus_Redlining_Agent_Writeup.docx)
- **Stack:** FastAPI + React (Vite) + OpenAI structured outputs + Postgres (Neon)

---

## What it does

Given a contract and a 7-rule playbook, the agent:

1. Splits the contract into numbered clauses.
2. Works out which playbook rules govern each clause.
3. Checks every threshold rule with arithmetic, in Python.
4. Reads the remaining clauses with a model, requiring a supporting quote.
5. Drafts replacement language for each confirmed deviation.
6. Decides which findings it may auto-suggest and which a human must review.

## Architecture

Six steps, three of them deterministic:

```
React UI
   │  POST /api/review
   ▼
FastAPI orchestrator
 1. Clause Segmenter      [Python]  split into numbered clauses
 2. Rule Matcher          [LLM]     clause -> governing playbook rules (one batched call)
 3. Numeric Gate          [Python]  extract the right number, compare to threshold
 4. Compliance Checker    [LLM]     only where arithmetic cannot decide; runs concurrently
 5. Redline Drafter       [LLM]     replacement language for confirmed deviations; concurrent
 6. HITL Classifier       [Python]  evidence -> confidence tier, severity, routing
   ▼
Findings grouped by what the reviewer needs to do
```

The directory layout mirrors this, and the split between the two kinds of step is the
top-level boundary rather than a comment:

```
backend/app/
├── orchestrator.py        the only module that knows the order of the work
│
├── tools/                 DETERMINISTIC — no model, no network, no API key
│   ├── segmenter.py       step 1   contract text -> numbered clauses
│   ├── numeric_gate.py    step 3   clause + rule -> arithmetic verdict
│   ├── vagueness.py                clause -> the hedging it relies on
│   ├── document.py                 uploaded PDF/Word/text -> contract text
│   └── hitl.py            step 6   evidence -> tier, severity, who decides
│
├── agents/                MODEL-BACKED — one prompt and one schema each
│   ├── rule_matcher.py    step 2   which rules govern which clauses
│   ├── compliance.py      step 4   does this clause breach this rule
│   └── redliner.py        step 5   replacement text for a clause
│
├── domain/                types, and the 7 playbook rules as data + lookup
├── llm/                   OpenAI client wrapper and prompt templates
├── storage/               Postgres: pool, schema, and the review repository
├── api/                   routes and transport DTOs
└── data/                  sample contract and a deliberately vague draft
```

Everything under `tools/` is callable on its own and unit-tested without a key, which is why
the offline suite runs in about a second. Two of those tools *overrule* the model rather than
serve it: `numeric_gate` settles a rule by arithmetic before the model is asked, and
`vagueness` pulls confidence down whatever the model claims about itself.

### Two decisions worth calling out

**The numeric gate runs before the model, not as a tool the model calls.** For the four
threshold rules, Python extracts the number and does the comparison itself. When that
succeeds the verdict involves no model judgment at all, which is what makes the top
confidence tier meaningful rather than a repackaged model self-report. If no number can be
read, the clause falls through to the model and lands in a lower tier instead.

The hard part is picking the *right* number. Clause 1 of the sample contract contains four
quantities (12 months, 12-month, 10 days, 7 days) governed by two different rules, so each
number is tied back to its rule through anchor phrases rather than by position.

**Rule matching is model-based, not a keyword table.** A keyword map would work on the
shipped sample and match nothing the moment someone pastes a different contract, failing
silently. A keyword fallback is retained only for when the model call itself errors.

## How confidence works

Two independent axes. Collapsing them into one score would hide the cases a reviewer most
needs to see.

**Confidence — how sure are we?**

| Tier | Basis | Behaviour |
|------|-------|-----------|
| High | Arithmetic against a playbook threshold | Auto-suggest a redline |
| Medium | Model found unambiguous wording and quoted it | Auto-suggest, marked for a look |
| Low | Model unsure, or asserted a deviation without quoting support | Flag for a human |

**Severity — how bad is it?** Taken from the playbook's own rationale. Payment terms,
liability cap, indemnification and data ownership are escalation-worthy; notice-period gaps
are negotiable.

So a deviation can be certain but minor (Net 15 payment terms), or uncertain but serious if
real (a vague data-rights clause). Both get surfaced differently.

Three deliberate guardrails:

- A **low-confidence pass is not an approval.** "Probably fine" is routed to a human, because
  silently approving is the failure this tool exists to prevent.
- A **deviation asserted without a supporting quote is downgraded**, however confident the
  model claims to be, since a reviewer cannot verify it at a glance.
- A clause **no rule covers** is reported as uncovered rather than as compliant, which also
  surfaces gaps in the playbook.

## How this was built, and where the AI got it wrong

This was built with Claude Code. Every module here was AI-generated, and both of the bugs
below were mine to catch rather than the tool's: Claude wrote plausible code, wrote tests that
passed against it, and was wrong anyway in ways that only showed up in the output.

That is the useful lesson from the build. The AI is reliable at the parts where correctness is
local — a regex, an async fan-out, a React component — and unreliable exactly where a decision
spans two places at once, or where the right answer depends on knowing how a model behaves in
practice rather than how the code reads. Both bugs sit in that second category, and neither was
caught by a test, because the AI wrote tests that encoded the same wrong assumption as the code.

The working pattern that caught them was to stop reading the diff and start reading the
*product output* against the sample data, line by line, asking what a reviewer would do with
each finding.

### Bug 1 — two redlines on one clause, each undoing the other

Clause 1 breaches two rules at once: a 10-day non-renewal notice and a 7-day termination
notice, both short of the 30-day minimum. Claude drafted redlines per clause-rule pair, which
reads perfectly sensibly one function at a time — and produced two separate replacements. Since
each replacement rewrites the *whole* clause, they were mutually exclusive:

- the auto-renewal redline fixed 10 → 30 days and kept `terminate for convenience upon 7 days`
- the termination redline fixed 7 → 30 days and kept `non-renewal at least 10 days`

A reviewer pasting either one would fix one violation and silently ship the other. The unit
tests passed throughout, because each redline was individually correct — the bug only exists
in the relationship between two findings, which is precisely what a per-function test cannot
see and what the AI had no reason to consider while writing either one.

**Fix:** drafting is now grouped by clause, with every breached rule in one call, so a clause
gets a single replacement satisfying all of them. The UI labels it, and a regression test
asserts clause 1 yields one text containing neither `7 days` nor `10 days`.

### Bug 2 — trusting the model to report its own confidence

Asked to build confidence handling, Claude did the obvious thing: have the model return a
confidence score and threshold on it. That is the design almost everyone reaches for, and it
looked fine in review. It never fired once.

Against a deliberately vague draft, the model returned:

| Quoted evidence | Confidence | Verdict |
|---|---|---|
| "a commercially reasonable amount" | 0.8 | violation |
| "reasonable prior written notice, to be determined" | 0.9 | violation |
| "such jurisdiction as the parties may mutually determine" | 0.9 | **no violation** |

Self-reported confidence clustered at 0.8–0.9 no matter how little the clause committed to.
The last row is the dangerous one: a clause naming no jurisdiction at all was confidently
cleared. A threshold sitting on top of that number inherits its miscalibration, so the
uncertainty feature was decorative.

This is the more interesting of the two failures, because the code was not buggy. It did
exactly what it said. The wrong assumption was about how the model behaves, which is not
visible in the source at all — only in what comes back when you run it on input designed to
be genuinely unclear.

**Fix:** the model no longer judges its own certainty in either direction. Arithmetic already
overrode confidence upward; a deterministic vagueness check now overrides it downward. When a
clause defers its substance to an outside standard ("customary", "commercially reasonable",
"as the parties may determine"), no verdict can be read off the text, so it is routed to a
human whatever the model claims.

Measured before and after, unchanged on the real contract and inverted on the vague one:

| | Sample contract | Vague draft |
|---|---|---|
| Before | 7 auto-suggested, 0 flagged | 4 auto-suggested, 0 flagged |
| After | 7 auto-suggested, 0 flagged | 0 auto-suggested, 5 flagged |

Over-flagging is the safe error here: the cost is a reviewer glancing at a clause, against the
cost of silently approving one nobody read.

## Running locally

Requires Python 3.11+ and Node 18+.

```bash
# 1. Configure
cp .env.example .env          # then add your OPENAI_API_KEY

# 2. Backend
cd backend
python -m venv .venv
.venv/Scripts/activate         # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload  # http://127.0.0.1:8000

# 3. Frontend (separate terminal)
cd frontend
npm install
npm run dev                    # http://localhost:5173, proxies /api to the backend
```

For a production-style run, `npm run build` emits the UI into `backend/app/static` and
FastAPI serves everything on one origin at `http://127.0.0.1:8000`.

## Tests

```bash
cd backend && .venv/Scripts/python -m pytest -q
```

The suite covers the deterministic layer and **runs without an API key**, which is the point:
segmentation, number extraction and the routing logic are all verifiable without a model in
the loop. It pins the cases most likely to break — clause 1's two competing notice periods,
`THREE (3) MONTHS` in caps, never comparing days against months — plus the full
confidence/severity truth table.

## Deploying

`render.yaml` describes the service. Set `OPENAI_API_KEY` in the dashboard; it is never
committed. The health check is `/api/health`, which also reports whether a key is configured.

Note: Render's free tier sleeps after inactivity and takes roughly 50 seconds to wake, so
open the URL a few minutes before any demo.

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Status, and whether the key and database are configured |
| GET | `/api/playbook` | The 7 rules |
| GET | `/api/playbook/export` | The shipped playbook as JSON, as a starting point |
| POST | `/api/playbook/validate` | Check a custom playbook before using it |
| GET | `/api/samples` | Sample contract and an intentionally ambiguous draft |
| POST | `/api/extract` | Read an uploaded PDF, Word or text file into contract text |
| GET | `/api/upload-info` | Accepted file types and size limit |
| POST | `/api/review` | Run a review; body `{ "contract_text": "..." }`, optional `?label=` |
| GET | `/api/reviews` | Past reviews, newest first |
| GET | `/api/reviews/{id}` | Reload one stored review with its findings and contract |
| DELETE | `/api/reviews/{id}` | Remove a stored review |

## Bringing your own playbook

The shipped playbook is a default, not a fixture. A different one can be loaded from the rail
as JSON, validated before use, and passed with a review.

Rules are **structured data, not prose**, and that is the whole design decision. A rule typed
as a sentence can only ever be judged by the model. A rule that states its threshold, unit and
anchor phrases can still be settled by arithmetic, which is what keeps findings on the verified
tier. So a numeric rule without anchors is rejected with an explanation rather than quietly
accepted and demoted to model judgment.

Anchors are the phrases that tie a number to a rule. They exist because a clause can hold
several numbers governed by different rules, which is exactly what clause 1 of the sample
contract does.

A worked example, entirely outside the shipped rules:

```json
[
  {
    "id": "warranty_period",
    "title": "Warranty period",
    "text": "Vendor must warrant the services for at least 6 months.",
    "rationale": "A short warranty shifts defect risk onto the customer.",
    "rule_type": "numeric",
    "default_severity": "serious",
    "threshold": 6,
    "unit": "months",
    "comparison": "at_least",
    "anchors": ["warrant", "warranty"]
  }
]
```

Against "Vendor warrants the services for a period of 3 months", that produces a **verified**
finding: 3 months against a 6-month minimum, decided by arithmetic with no model involved,
exactly like a shipped rule.

Each stored review keeps a snapshot of the rules it was judged against. Without that, editing a
playbook would silently rewrite the meaning of every past review, which is unacceptable in an
audit trail.

## Uploading a contract

Drop a PDF, Word document or text file onto the page, or paste text directly. Upload never
runs a review on its own: the extracted text lands in the editor first, so you can see what
was actually read out of the file and fix it before spending a model call on it.

The awkward part is not reading the bytes, it is line breaks. The segmenter finds clauses by
looking for "1." at the start of a line, and PDF extraction routinely returns a paragraph as
one long wrapped line with the numbering buried mid-sentence. Extraction is therefore always
followed by normalisation that puts clause numbers back at the start of their own line, and
the tests assert on *clauses found*, not characters extracted, because that is the failure
that would otherwise pass silently.

## Persistence

Every review is written to Postgres with its findings, giving the tool an audit trail: what the
agent concluded about which draft, when, and which findings it declined to act on. The UI lists
past reviews and reloads any of them with the original contract text.

Two deliberate choices:

- **Persistence is optional.** With no `DATABASE_URL` the pool never opens and everything works
  as before, which is why the offline test suite still runs with no database and no API key.
- **Writes are best-effort.** If the database is unreachable, the failure is logged and the
  reviewer still gets the findings already on their screen. Losing the audit trail is bad;
  losing the review someone is mid-way through reading is worse.

Two Neon specifics the code handles, both of which fail confusingly otherwise: the `-pooler`
host runs pgbouncer, so asyncpg's prepared-statement cache is disabled, and the `sslmode` and
`channel_binding` query parameters are libpq options that asyncpg does not understand, so they
are stripped and TLS is configured explicitly.

## A note on the playbook

The liability-cap rule is worded "must not exceed 12 months of fees", but the accompanying
answer key treats a 3-month cap as violating a 12-month *minimum*. Those are opposite
readings. It is implemented as a minimum, because Zycus is the customer and the clause caps
the vendor's liability, so a smaller cap means less recourse. The ambiguity is worth raising
with whoever owns the playbook, and it is flagged in `backend/app/domain/playbook.py`.
