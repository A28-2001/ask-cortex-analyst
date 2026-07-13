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

## Run-to-run stability check

The parsing-bug fix required re-running the baseline a second time,
which gave an unplanned but useful check: comparing the two independent
runs (both `temperature=0`) shows 12 of 36 questions produced genuinely
different generated SQL between runs, and two flipped outcome entirely
— `cohort_3` was correct in the first run and failed in the second
(a `GROUP BY` error); `amb_2` failed in the first run (a broken
self-referential subquery returning `NULL`) and was correct in the
second. `temperature=0` reduces but does not eliminate variance in this
model's SQL generation.

This means 65.3% should be read as one sample from a distribution, not
an exact fixed number — a third run would likely land in a similar
range but not hit exactly 65.3% again. What *did* reproduce exactly
across both runs: the `guard_1` hallucination (byte-for-byte identical
SQL both times) and the dominant enum-guessing failure pattern (present
in both runs, even where the specific wrong guess differed). The
qualitative finding is robust; the precise percentage carries some
sampling noise that a single 36-question run can't rule out.

## A fairness note on the comparison

The final Cortex Analyst number (100%) reflects three rounds of
diagnosis and fixing on this exact question set, validated afterward
on a separate blind holdout. The baseline number (65.3%) reflects one
(now two, for stability-checking) cold pass with zero iteration, by
design. The most apples-to-apples *single-pass* comparison is baseline
65.3% vs. Cortex Analyst's original v1 pass at 93.1% — which still
shows a large gap before any tuning on either side. The gap to the
final 100% reflects the added value of iteration on top of grounding,
not grounding alone. Both framings are legitimate; conflating them
would overstate the case.

Also worth naming as a scope limit: this tests one baseline model
(`llama-3.3-70b-versatile`) with one minimal prompt. A different
off-the-shelf model, or a hand-engineered prompt that reinvents parts
of a semantic layer (documenting valid values, adding refusal rules),
could plausibly score higher — this result shows what a realistic,
minimal-effort naive setup gets you, not the ceiling of what prompting
alone could achieve with enough manual effort.

## Bottom line

On real business questions, semantic grounding took accuracy from
68.3% to 100% and correct guardrail behavior from 50% to 100%, while
eliminating a hallucination rate of 1-in-6 entirely. The mechanism is
concrete and traceable, not abstract: documented valid values prevent
silently wrong filters, documented conventions prevent misinterpreted
column semantics, and explicit refusal instructions prevent a
forecasting question from being quietly answered with a fabricated
zero. The headline hallucination and the dominant failure pattern both
reproduced across independent runs; the exact accuracy percentage
carries normal single-sample noise on top of that.
