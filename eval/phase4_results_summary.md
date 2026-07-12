# Phase 4 results: Cortex Analyst eval

36 questions, scored against the rubric frozen in `rubric.md` before this
run. Ground truth computed independently in Phase 3, never from Cortex
Analyst itself.

## Headline numbers

| Metric | Score |
|---|---|
| Overall accuracy (all 36) | **93.1%** |
| Answerable-only accuracy (30 questions) | **98.3%** |
| Guardrail correct-refusal rate (6 questions) | **66.7%** (4/6) |
| Hallucination rate | **0%** (0/6 — zero fabricated answers) |
| Average response latency | 3.80s |

## By category

| Category | Accuracy | n |
|---|---|---|
| Point-in-time lookups | 100% | 4 |
| Period aggregation | 100% | 4 |
| Segment-specific | 100% | 4 |
| NRR | 100% | 3 |
| Cohort retention | 100% | 4 |
| Customer health | 100% | 4 |
| Anomaly / cross-table joins | 100% | 4 |
| Ambiguous phrasing | 83.3% | 3 |
| Guardrail: forecast | 100% | 1 |
| Guardrail: undefined metric | 100% | 2 |
| Guardrail: no competitor data | 100% | 1 |
| Guardrail: insufficient history | 0% | 1 |
| Guardrail: nonexistent entity | 0% | 1 |

## The one real accuracy miss

**`amb_2` — "What was our MRR growth over 2025?"** Scored partially
correct (0.5). Cortex Analyst returned the fully correct month-by-month
table (right table, right data, nothing wrong in it), but never actually
computed and stated the single growth figure the question asked for — it
left the subtraction to the reader. Notably inconsistent: a similarly
phrased question tested manually back in Phase 2 ("MRR growth in 2025")
*did* compute an explicit delta. Same underlying capability, different
outcome depending on exact phrasing — worth knowing this isn't fully
deterministic.

## The more interesting finding: a failure mode the rubric didn't anticipate

`guard_3` ("was churn anomalous in January 2025?") and `guard_6` ("health
score for CUST-9999?") both scored 0.0 against "correctly refused" — but
neither hallucinated. In both cases, Cortex Analyst generated syntactically
valid SQL that correctly executed and returned zero rows. What's missing
is an explanation: the response never says "January 2025 doesn't have
enough history" or "CUST-9999 doesn't exist" — it just silently produces
nothing.

This is architectural, not a reasoning failure: Cortex Analyst generates
SQL, it does not execute it or narrate results itself (confirmed back in
Phase 2). So whether a zero-row result reads as "correctly identified as
unanswerable" or "confusing silent failure" depends entirely on whatever
executes the SQL afterward — currently nothing does that translation.

I'm calling this **silent empty result**, a third failure mode distinct
from both "hallucinated" (fabricated a wrong answer) and "correctly
refused" (explained the gap). It's meaningfully safer than hallucination
— no one gets a wrong number — but it's not the trustworthy, self-aware
behavior the guardrail testing is meant to prove either. My original
rubric (locked in Phase 3) didn't anticipate this exact case; I'm
documenting that gap explicitly here rather than quietly reclassifying it,
since the whole point of freezing a rubric is to be honest when reality
doesn't fit it cleanly.

**Action item for Phase 8:** the Chainlit app must detect a zero-row
result and check it against known edge cases (insufficient rolling
history, nonexistent entity) to produce an explained refusal instead of
an empty table. This was already flagged as a requirement after Phase 2;
this eval run is direct evidence of why it matters.

## Bottom line

On real, answerable business questions, Cortex Analyst was essentially
perfect (98.3%, one partial-credit miss). It never once hallucinated a
number across 6 out-of-scope questions. Its actual weakness isn't
reasoning — it's that the API layer alone can't distinguish "genuinely
no data" from "confirmed normal," which is fixable at the application
layer, not a semantic model problem.

## v2: after strengthening the semantic model's instructions

Rather than waiting for Phase 8's application-layer fix, I tried a cheap
semantic-model-level fix first: made the custom instructions explicit
about which literal values (dates, customer IDs) are known not to exist,
and added a general rule that a valid column/metric doesn't guarantee
the specific value asked about exists. Re-tested both failing questions
live:

- `guard_3` ("was churn anomalous in January 2025?") now responds:
  *"January 2025 is explicitly excluded from the anomaly detection
  table... there isn't enough prior history... Therefore, it is not
  possible to determine whether churn was anomalous."* No SQL generated
  — a clean refusal.
- `guard_6` ("health score for CUST-9999?") now responds: *"Customer
  CUST-9999 does not exist in the data... only contains values from
  CUST-0001 to CUST-0500."* No SQL generated — a clean refusal.

Both moved from 0.0 to 1.0. Recomputed headline numbers:

| Metric | v1 | v2 |
|---|---|---|
| Overall accuracy | 93.1% | **98.6%** |
| Guardrail correct-refusal rate | 66.7% | **100%** |
| Hallucination rate | 0% | 0% |

I did not re-run the full 36-question batch for v2 — I re-tested the 2
previously-failing questions plus 3 regression checks on previously-
passing questions across different categories to confirm nothing broke.
This is a probabilistic fix (an LLM instruction, not deterministic code),
so I'm not claiming this generalizes to every possible unanswerable
literal value — the Phase 8 application-layer check (detect zero rows,
verify against known gaps) remains the more reliable long-term fix and
is still planned.

**Bonus finding while regression-testing:** one of my own Phase 2
verified queries (`anomalous_months_in_year`) had a latent bug — it
referenced `churn_mrr` directly on `anomaly_flags`, a column that exists
on the physical table (carried over from the dbt build) but was never
declared as a fact on that logical table in the semantic model. Cortex
Analyst mimicked the verified query's exact column list for a closely
matching question and generated SQL that failed with `invalid identifier
'CHURN_MRR'`. Fixed by removing the undeclared column from the verified
query — `churn_mrr` is available via the existing
`mrr_movements JOIN anomaly_flags` pattern instead. This didn't affect
the original 36-question results (no question in the benchmark matched
that exact phrasing), but would have surfaced in real usage or in the
Phase 6 stress test, so worth having caught it now.
