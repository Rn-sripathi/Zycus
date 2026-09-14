# Sample contracts

Drop any of these onto the app to test upload. They are generated from the text
fixtures in `backend/app/data/`, typeset like real contracts so the body wraps
and clause numbers land mid-line, which is the case PDF extraction has to survive.

| File | What it is | Expected result |
|------|-----------|-----------------|
| `Northwind_Vendor_Services_Agreement.pdf` | The counterparty draft with the planted issues | 8 clauses, 7 deviations, 4 to escalate, 2 clauses no rule covers |
| `Northwind_Vendor_Services_Agreement.docx` | The same contract as Word | Identical findings |
| `Northwind_Ambiguous_Draft.pdf` | A deliberately vague draft | 5 clauses, all 5 flagged for a human, none auto-suggested |

The ambiguous draft is the one to open if you want to see the uncertainty
handling do something. Every clause in it hides behind wording like "a
commercially reasonable amount", so nothing reaches the auto-suggest tier.

Regenerate them with the script referenced in the repository history if the
underlying fixtures change.
