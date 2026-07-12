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
