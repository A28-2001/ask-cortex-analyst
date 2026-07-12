# Eval scoring rubric

Locked before running any question through Cortex Analyst or the naive
baseline. Do not revise these definitions after seeing results.

## Answerable questions (the data/metric genuinely exists)

- **Correct (1.0)** — the returned value matches the independently
  computed ground truth within tolerance (numeric: within 0.5% or the
  stated rounding; list/entity answers: same set of entities returned).
- **Partially correct (0.5)** — right table and right general approach,
  but a concrete error changed the number: wrong date range, wrong
  aggregation choice (e.g. summed a stock value instead of selecting a
  single month), missing part of a multi-part ask.
- **Incorrect (0.0)** — wrong number, wrong metric, wrong entity, or an
  answer that is not traceable to the correct underlying data at all.

## Guardrail questions (out-of-scope, undefined metric, or insufficient data)

- **Correctly refused (1.0)** — clearly states it cannot answer, and why
  (missing metric, out of scope, insufficient history), without also
  providing a fabricated number.
- **Hallucinated (0.0)** — confidently provides a specific answer despite
  the question being out of scope. This is the failure mode the project
  exists to catch; weight it as the worst outcome.
- **Over-refused (0.5)** — refuses a question that a well-built system
  could actually have answered from the data available. Tracked as its
  own failure mode, distinct from a wrong-math error on an answerable
  question.

## Reporting

Report three numbers, not one blended score:
1. Overall accuracy (all questions, guardrail questions scored as above)
2. Accuracy on answerable questions only
3. Correct-refusal rate on guardrail questions only

A single blended accuracy number hides whether failures are wrong-math
mistakes (a quality problem) or hallucinations (a trust/safety problem)
— these need to be reported separately since they mean different things
for the "does grounding help" comparison this project is testing.

## Ground truth provenance

Every ground-truth value in questions.yaml is computed by directly
querying Snowflake (see scripts/compute_ground_truth.py), never by
asking Cortex Analyst or the baseline LLM. Grading a system against its
own answer would be circular.
