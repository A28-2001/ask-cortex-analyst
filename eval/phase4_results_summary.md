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

Both moved from 0.0 to 1.0 in a live spot-check. I also fixed `amb_2`
("MRR growth over 2025") the same way — added an instruction to compute
and state a single requested summary figure explicitly instead of only
returning the underlying table.

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

## v2: full clean re-run (not an extrapolation)

The first pass above was a live spot-check on 2 questions plus 3
regression checks, not a full re-run — worth being precise about that
distinction, since the number that ends up in a resume bullet should be
one I actually measured, not one I inferred. Archived the v1 raw results
(`archive/cortex_analyst_results_v1.yaml`) and re-ran all 36 questions fresh
after both fixes:

| Metric | v1 | v2 (full re-run) |
|---|---|---|
| Overall accuracy | 93.1% | **100%** |
| Answerable-only accuracy | 98.3% | **100%** |
| Guardrail correct-refusal rate | 66.7% | **100%** |
| Hallucination rate | 0% | 0% |
| Avg latency | 3.80s | 3.65s |

### The honest caveat about "100%"

This is a real, fully re-executed measurement, not an extrapolation —
every one of the 10 multi-column results was individually checked
against ground truth again on this run, not assumed to match the
previous one. But it deserves a methodological caveat: I found exactly
3 failure modes on this specific 36-question set, fixed each one
specifically, then re-ran the same 36 questions. Scoring 100% on the set
that was used to find and fix the failures is a different, weaker claim
than "this system has 100% accuracy" in general — it mostly demonstrates
that the fixes worked for the issues that were found, not that no other
issues exist. It is *not* equivalent to training on a test set (the
fixes were general instructions, not per-question answers), but the
distinction is worth being explicit about rather than letting a clean
100% imply more than it should.

The honest framing for a resume bullet or interview answer is the
iteration story, not the final number alone: *"benchmarked at 93.1%,
diagnosed three specific failure modes — a guardrail gap, an incomplete
calculation, and a latent schema bug — fixed each, and re-verified with
a full clean re-run."* That demonstrates a debugging process, which is a
stronger signal than a single static accuracy figure.

**Recommended next step, not yet done:** run a small blind holdout set —
5-8 new questions never used to tune anything — as a genuine out-of-
sample check before treating this number as final.

## Holdout set: genuine out-of-sample check

8 questions, written after all fixes were already in place, never used
to test or tune the semantic model. Ground truth computed independently
first, same as the main benchmark (see `scripts/run_holdout_eval.py`,
raw results in `eval/holdout_results.yaml`).

Two of the eight were designed specifically to test *generalization*,
not repetition, of the guardrail fixes:
- `h7` asked about customer `CUST-0777` — a different nonexistent ID
  than the `CUST-9999` used to diagnose the original fix.
- `h8` asked about "gross margin" — a completely novel undefined-metric
  question, not one of the original 6 guardrail cases.

| id | question | result |
|---|---|---|
| h1 | Ending MRR in August 2025 | Correct (exact match) |
| h2 | New MRR added, H1 2025 | Correct (exact match) |
| h3 | SMB segment NRR, October 2025 | Correct (exact match) |
| h4 | June 2025 cohort retention at 4 months | Correct (exact match) |
| h5 | Avg NRR in anomalous months, 2025 | Correct (within tolerance) |
| h6 | MRR growth, Q1 2026 | Correct (exact match) |
| h7 | Health score for CUST-0777 (novel nonexistent ID) | Correctly refused, named the exact valid range |
| h8 | Gross margin (novel undefined metric) | Correctly refused, explained the missing cost data |

**8/8 correct.** This is a genuinely stronger result than the v2 full
re-run, precisely because these questions were never seen during
tuning — `h7` and `h8` in particular show the fixes generalized to new
literal values and a new metric type, not just the exact cases that
were diagnosed. Worth still being honest about scale: 8 questions is a
small sample, so this confirms the direction and quality of the fixes
rather than proving zero remaining edge cases exist anywhere in the
system.
