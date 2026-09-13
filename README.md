# Zycus Redlining Agent

Reviews a counterparty-proposed contract against the Zycus standard playbook, proposes
specific replacement language for each deviation, and separates findings it can verify
from findings a human should judge.

Built for the Zycus Product Intern (AI PM track) take-home, Track B.

- **Live app:** _add your deployed URL here_
- **Stack:** FastAPI + React (Vite) + OpenAI structured outputs

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

The directory layout mirrors this: each step is one module in `backend/app/pipeline/`.

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
| GET | `/api/health` | Status and whether a key is configured |
| GET | `/api/playbook` | The 7 rules |
| GET | `/api/samples` | Sample contract and an intentionally ambiguous draft |
| POST | `/api/review` | Run a review; body `{ "contract_text": "..." }` |

## A note on the playbook

The liability-cap rule is worded "must not exceed 12 months of fees", but the accompanying
answer key treats a 3-month cap as violating a 12-month *minimum*. Those are opposite
readings. It is implemented as a minimum, because Zycus is the customer and the clause caps
the vendor's liability, so a smaller cap means less recourse. The ambiguity is worth raising
with whoever owns the playbook, and it is flagged in `backend/app/domain/playbook.py`.
