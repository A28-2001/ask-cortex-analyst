import os
import sys
import yaml

sys.path.insert(0, os.path.dirname(__file__))
from run_baseline_eval import ask_baseline, execute_sql

QUESTIONS_PATH = os.path.join(os.path.dirname(__file__), "..", "eval", "stress_test_questions.yaml")
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "..", "eval", "stress_test_baseline_results.yaml")

with open(QUESTIONS_PATH) as f:
    questions = yaml.safe_load(f)["questions"]

results = []
for q in questions:
    print(f"\n{'='*80}\n[{q['id']}] {q['question']}\n{'-'*80}")
    sql, raw, latency = ask_baseline(q["question"])
    print(f"generated_sql: {'YES' if sql else 'none'}")
    if sql:
        print(sql)
        exec_result = execute_sql(sql)
        print("rows:", exec_result["rows"], "error:", exec_result["error"])
    else:
        exec_result = {"rows": None, "error": None}
    print(f"raw_response: {raw}")

    results.append({
        **q, "generated_sql": sql, "raw_response": raw,
        "actual_rows": exec_result["rows"], "exec_error": exec_result["error"],
        "latency": round(latency, 2),
    })

with open(RESULTS_PATH, "w") as f:
    yaml.dump({"results": results}, f, sort_keys=False, width=100, allow_unicode=True)
print(f"\nWrote results to {RESULTS_PATH}")
