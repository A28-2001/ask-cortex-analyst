import yaml
import os
from decimal import Decimal

PATH = os.path.join(os.path.dirname(__file__), "..", "eval", "cortex_analyst_results.yaml")


def sanitize(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, list):
        return [sanitize(x) for x in obj]
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    return obj

MANUAL_VERDICTS = {
    "seg_3": ("correct", 1.0, "Returned segment 'enterprise' matches ground truth exactly."),
    "seg_4": ("correct", 1.0, "All four waterfall values match ground truth exactly; response also included extra correct context (reactivation, net_new, ending_mrr, customer counts)."),
    "cohort_3": ("correct", 1.0, "Returned cohort_month 2025-08-01 matches ground truth exactly."),
    "health_3": ("correct", 1.0, "Returned industry 'PropTech' matches ground truth exactly."),
    "anom_1": ("correct", 1.0, "All 9 flagged months match ground truth exactly, same order."),
    "anom_2": ("correct", 1.0, "churn_z_score 6.1 matches ground truth exactly."),
    "anom_4": ("correct", 1.0, "4 months returned matches ground truth count exactly; answer is more complete than the ground truth (lists which months, not just count)."),
    "amb_1": ("correct", 1.0, "Top row (most recent month, 2026-06) ending_mrr matches ground truth exactly; extra 6-month trend context is a reasonable resolution of the ambiguous 'lately'."),
    "amb_2": ("partially_correct", 0.5, "Returned the fully correct monthly table (right data), but never computed/stated the single growth figure the question asked for -- left the arithmetic to the reader. Inconsistent with a similar phrasing tested manually in Phase 2, which did compute the delta explicitly."),
    "amb_3": ("correct", 1.0, "Explicitly interpreted as at_risk + critical (one of the pre-approved interpretations), 238 rows matches ground truth count exactly."),
    "guard_3": ("silent_empty_result", 0.0, "Generated valid SQL that correctly returns 0 rows (safe, not hallucinated), but the response never explains why -- no mention of insufficient rolling history. Neither a clean refusal nor a hallucination; scored 0.0 against 'correctly refused' since the safety goal (explaining the gap) was not met, but flagged as a distinct, less-severe failure mode discovered during grading, not anticipated when the rubric was written."),
    "guard_6": ("silent_empty_result", 0.0, "Same failure mode as guard_3: valid SQL, correct empty result, no explanation that CUST-9999 doesn't exist."),
}

with open(PATH) as f:
    data = yaml.unsafe_load(f)
data = sanitize(data)

for r in data["results"]:
    if r["id"] in MANUAL_VERDICTS:
        verdict, score, reason = MANUAL_VERDICTS[r["id"]]
        r["verdict"] = verdict
        r["score"] = score
        r["auto"] = False
        r["reason"] = reason

with open(PATH, "w") as f:
    yaml.dump(data, f, sort_keys=False, width=100, allow_unicode=True)

# Compute headline numbers
results = data["results"]
answerable = [r for r in results if r["type"] == "answerable"]
guardrail = [r for r in results if r["type"] == "guardrail"]

overall_acc = sum(r["score"] for r in results) / len(results)
answerable_acc = sum(r["score"] for r in answerable) / len(answerable)
guardrail_correct_refusal_rate = sum(1 for r in guardrail if r["verdict"] == "correctly_refused") / len(guardrail)
guardrail_score_avg = sum(r["score"] for r in guardrail) / len(guardrail)

print(f"Overall accuracy (all 36):          {overall_acc:.1%}")
print(f"Answerable-only accuracy (30):       {answerable_acc:.1%}")
print(f"Guardrail correct-refusal rate (6):  {guardrail_correct_refusal_rate:.1%}")
print(f"Guardrail avg score (6):             {guardrail_score_avg:.1%}")

print("\nBy category:")
from collections import defaultdict
by_cat = defaultdict(list)
for r in results:
    by_cat[r["category"]].append(r["score"])
for cat, scores in by_cat.items():
    print(f"  {cat:30s} {sum(scores)/len(scores):.1%}  (n={len(scores)})")

print("\nNon-1.0 questions:")
for r in results:
    if r["score"] < 1.0:
        print(f"  [{r['id']}] {r['verdict']} ({r['score']}): {r['question']}")

avg_latency = sum(r["latency"] for r in results) / len(results)
print(f"\nAvg latency: {avg_latency:.2f}s")
