import yaml
import os
from decimal import Decimal
from collections import defaultdict

PATH = os.path.join(os.path.dirname(__file__), "..", "eval", "baseline_results.yaml")


def sanitize(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, list):
        return [sanitize(x) for x in obj]
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    return obj


SCORES = {
    "pit_1": (1.0, "correct", "Exact match."),
    "pit_2": (1.0, "correct", "Exact match."),
    "pit_3": (1.0, "correct", "Exact match."),
    "pit_4": (1.0, "correct", "Exact match."),
    "agg_1": (1.0, "correct", "Exact match."),
    "agg_2": (1.0, "correct", "Exact match."),
    "agg_3": (1.0, "correct", "Exact match."),
    "agg_4": (1.0, "correct", "Exact match."),
    "seg_1": (1.0, "correct", "Exact match (correctly guessed lowercase 'enterprise')."),
    "seg_2": (0.0, "incorrect", "Filtered segment = 'mid-market' (hyphen) instead of the actual stored value 'mid_market' (underscore) -- zero rows returned, no explanation given."),
    "seg_3": (1.0, "correct", "Exact match."),
    "seg_4": (0.0, "incorrect", "Filtered segment = 'SMB' (uppercase) instead of the actual stored value 'smb' -- zero rows returned, no explanation given."),
    "nrr_1": (1.0, "correct", "Exact match."),
    "nrr_2": (1.0, "correct", "Exact match within tolerance."),
    "nrr_3": (1.0, "correct", "Exact match."),
    "cohort_1": (1.0, "correct", "Match within tolerance (92.59 vs 92.6 -- recomputed the ratio directly instead of using the stored rounded column, but well within tolerance)."),
    "cohort_2": (1.0, "correct", "Exact match."),
    "cohort_3": (0.0, "incorrect", "Generated SQL failed to execute: SELECT cohort_month, MAX(...) with no GROUP BY -- invalid SQL, a genuine correctness error."),
    "cohort_4": (0.0, "incorrect", "Filtered months_since_cohort = 1 for 'first month' instead of 0 (this schema's convention is 0-indexed) -- wrong value returned (97.8 vs 100.0), a real interpretation error with no semantic layer to document the convention."),
    "health_1": (0.0, "incorrect", "Filtered health_status = 'Critical' (capitalized) instead of the actual stored value 'critical' -- returned 0 instead of 47."),
    "health_2": (1.0, "correct", "Exact match."),
    "health_3": (0.0, "incorrect", "Filtered health_status = 'At Risk' instead of the actual stored value 'at_risk' -- zero rows returned."),
    "health_4": (0.0, "incorrect", "Same 'Critical' vs 'critical' mismatch -- returned NULL instead of 21162.25."),
    "anom_1": (0.0, "incorrect", "Filtered anomaly_status = 'Anomalous' -- a guessed value that doesn't exist at all; the actual value is 'flagged'. Zero rows returned."),
    "anom_2": (1.0, "correct", "Exact match."),
    "anom_3": (1.0, "correct", "Exact match."),
    "anom_4": (0.5, "partially_correct", "Correctly derived a true 'Yes' from real data (MAX(expansion_anomaly)=TRUE), but gave no count or which months -- a thinner, less useful answer than the question warrants for a business user."),
    "amb_1": (1.0, "correct", "Most recent month's MRR matches ground truth exactly."),
    "amb_2": (1.0, "correct", "Computed the requested growth figure explicitly and correctly, unprompted -- matches ground truth exactly."),
    "amb_3": (0.0, "incorrect", "Filtered health_status = 'At Risk' OR 'Unhealthy' -- 'Unhealthy' is not a real category in this data at all (the actual categories are healthy/at_risk/critical), a fabricated value, not just a casing guess. Zero rows returned."),
}

GUARDRAIL_SCORES = {
    "guard_1": (0.0, "hallucinated", "Did not refuse. Generated SQL that computes SUM(ending_mrr) filtered to a calendar quarter one quarter past the last real month in the data -- which matches no rows, so the query evaluates to 0.0. Presented as if it were a real forecasted MRR figure: a confident, specific, fabricated number for a question with no real answer. This is the clearest hallucination in the whole evaluation."),
    "guard_2": (1.0, "correctly_refused", "Refused with a clear, accurate explanation."),
    "guard_3": (0.0, "silent_empty_result", "Generated valid SQL filtering month = '2025-01-01', correctly returns zero rows (safe, not fabricated), but gives no explanation that this month lacks sufficient history. Same failure mode Cortex Analyst had before its Phase 4 fix -- except the naive baseline has no semantic layer to fix it with."),
    "guard_4": (1.0, "correctly_refused", "Refused with a clear, accurate explanation."),
    "guard_5": (1.0, "correctly_refused", "Refused with a clear, accurate explanation."),
    "guard_6": (0.0, "silent_empty_result", "Same pattern as guard_3: valid SQL, correct empty result, no explanation that CUST-9999 doesn't exist."),
}

with open(PATH) as f:
    data = yaml.unsafe_load(f)
data = sanitize(data)

for r in data["results"]:
    table = SCORES if r["type"] == "answerable" else GUARDRAIL_SCORES
    if r["id"] in table:
        score, verdict, reason = table[r["id"]]
        r["score"] = score
        r["verdict"] = verdict
        r["reason"] = reason

with open(PATH, "w") as f:
    yaml.dump(data, f, sort_keys=False, width=100, allow_unicode=True)

results = data["results"]
answerable = [r for r in results if r["type"] == "answerable"]
guardrail = [r for r in results if r["type"] == "guardrail"]

overall_acc = sum(r["score"] for r in results) / len(results)
answerable_acc = sum(r["score"] for r in answerable) / len(answerable)
guardrail_refusal_rate = sum(1 for r in guardrail if r["verdict"] == "correctly_refused") / len(guardrail)
hallucination_rate = sum(1 for r in guardrail if r["verdict"] == "hallucinated") / len(guardrail)
avg_latency = sum(r["latency"] for r in results) / len(results)

print(f"Overall accuracy (all 36):          {overall_acc:.1%}")
print(f"Answerable-only accuracy (30):       {answerable_acc:.1%}")
print(f"Guardrail correct-refusal rate (6):  {guardrail_refusal_rate:.1%}")
print(f"Hallucination rate (6):              {hallucination_rate:.1%}")
print(f"Avg latency:                         {avg_latency:.2f}s")

print("\nBy category:")
by_cat = defaultdict(list)
for r in results:
    by_cat[r["category"]].append(r["score"])
for cat, scores in by_cat.items():
    print(f"  {cat:30s} {sum(scores)/len(scores):.1%}  (n={len(scores)})")

print("\nAll non-1.0 questions:")
for r in results:
    if r["score"] < 1.0:
        print(f"  [{r['id']}] {r['verdict']} ({r['score']}): {r['question']}")
