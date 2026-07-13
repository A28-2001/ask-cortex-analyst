# Phase 5 results: naive baseline (Groq, no semantic model)

Same 36 locked questions from Phase 3, same frozen rubric, same ground
truth. The only variable changed is grounding: `llama-3.3-70b-versatile`
via Groq, given only raw table/column names and types (`scripts/schema_only.py`)
— no business descriptions, no synonyms, no stock-vs-flow guidance, no
guardrail instructions, no verified examples. This is the control
condition the whole project exists to test against.

**Methodology note:** unlike Cortex Analyst, the baseline was not
iterated on after seeing failures — no prompt tuning, no added examples.
One harness bug was fixed (a parsing check that missed a refusal wrapped
in a code fence — see below), which is a measurement-accuracy fix, not
a change to the model's guidance, and the same standard applied
throughout this project's tooling.

## Headline numbers

| Metric | Naive baseline | Cortex Analyst (v1, first pass) | Cortex Analyst (v2, final) |
|---|---|---|---|
| Overall accuracy | **65.3%** | 93.1% | 100% |
| Answerable-only accuracy | **68.3%** | 98.3% | 100% |
| Guardrail correct-refusal rate | **50.0%** | 66.7% | 100% |
| Hallucination rate | **16.7%** | 0% | 0% |
| Avg latency | 1.27s | 3.80s | 3.65s |

The baseline is faster (no semantic model to parse), but that speed
comes with real correctness cost. This is the actual finding of the
project: grounding a text-to-SQL system in a semantic model doesn't
just marginally help, it's the difference between a system that never
hallucinates and one that fabricates specific wrong numbers roughly
1 in 6 times it's asked something it can't answer.

## The headline failure: a real hallucination

**`guard_1` — "What will our MRR be next quarter?"** The baseline did
not refuse. It generated:

```sql
WITH quarterly_mrr AS (...), next_quarter AS (
  SELECT MAX(quarter) AS current_quarter FROM quarterly_mrr
)
SELECT SUM(CASE WHEN DATE_TRUNC('quarter', month) =
  (SELECT current_quarter FROM next_quarter) + INTERVAL '1 quarter'
  THEN ending_mrr ELSE 0 END) AS next_quarter_mrr
FROM mrr_movements
```

This filters for a calendar quarter that doesn't exist in the data, so
the `CASE` never matches and `SUM` returns `0.0`. Presented without
caveat, this reads as "next quarter's MRR will be $0" — a confident,
specific, actively misleading number for a company currently doing
several million dollars in MRR. Cortex Analyst, given the same
question, explained plainly that forecasting is out of scope. This is
the clearest, most concrete evidence in the whole project for why
grounding matters: the failure mode isn't "no answer," it's a
plausible-looking wrong answer with no signal that anything is wrong.

## The dominant failure pattern: guessed enum values

9 of the baseline's 13 non-1.0 scores trace to exactly one root cause:
without documented valid values, the model guessed plausible-but-wrong
formatting for categorical filters, and Snowflake silently returned
zero rows or NULL rather than erroring:

| Question | Guessed value | Actual stored value |
|---|---|---|
| `seg_2` | `'mid-market'` | `mid_market` |
| `seg_4` | `'SMB'` | `smb` |
| `health_1`, `health_4` | `'Critical'` | `critical` |
| `health_3` | `'At Risk'` | `at_risk` |
| `anom_1` | `'Anomalous'` | `flagged` |
| `amb_3` | `'At Risk'` / `'Unhealthy'` | `at_risk` / `critical` (`'Unhealthy'` doesn't exist as a category at all) |

This is exactly the class of problem `sample_values` was built to
solve in the semantic model (Phase 2, hardened further after Phase 4).
The naive baseline has no equivalent — it's pure guesswork, and it's
right or wrong essentially by luck (it happened to guess lowercase
`'enterprise'` correctly in `seg_1`, but uppercase `'SMB'` incorrectly
in `seg_4` — no internal consistency, because there's nothing grounding
the guess). None of these failures produced an error message; every one
silently returned an empty or null result with no indication anything
was wrong, which is arguably worse than an outright crash for a
business user who might not think to double-check.

## Other genuine reasoning errors (not just formatting)

- **`cohort_4`** — asked for the May 2025 cohort's retention "in their
  first month." The baseline filtered `months_since_cohort = 1`; this
  schema's convention is that month 0 is the first month. A real
  interpretation error, not a casing guess — and exactly the kind of
  convention a semantic model's column descriptions exist to document
  (Cortex Analyst got this right, using the same 0-indexed convention,
  because the semantic model states it explicitly).
- **`cohort_3`** — generated SQL with an invalid `GROUP BY` (`SELECT
  cohort_month, MAX(...)` with no `GROUP BY cohort_month`), which
  failed to execute outright.

## Guardrail behavior: the same "silent empty result" gap, permanently

`guard_3` and `guard_6` show the exact failure mode Cortex Analyst had
*before* the Phase 4 fix — valid SQL, correctly empty result, no
explanation. The difference: Cortex Analyst's version was fixable with
a semantic model instruction. The naive baseline has no such layer, so
this gap is permanent unless the prompt itself is engineered around it
— which would mean building an ad hoc semantic layer by hand, the
thing Cortex Analyst already provides.

## Not everything the baseline did was bad

Worth being fair: it got all 4 point-in-time lookups, all 4 period
aggregations, and all 3 NRR questions exactly right, and — notably — it
computed the `amb_2` growth figure correctly and explicitly on its own,
without any instruction telling it to (something Cortex Analyst
initially got wrong before its own fix). General arithmetic and
straightforward single-table queries are not where this baseline
struggles; enum-value grounding and business-convention knowledge are.

## Bottom line

On real business questions, semantic grounding took accuracy from
68.3% to 100% and correct guardrail behavior from 50% to 100%, while
eliminating a hallucination rate of 1-in-6 entirely. The mechanism is
concrete and traceable, not abstract: documented valid values prevent
silently wrong filters, documented conventions prevent misinterpreted
column semantics, and explicit refusal instructions prevent a
forecasting question from being quietly answered with a fabricated
zero.
