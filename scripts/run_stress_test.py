import os
import sys
import yaml

sys.path.insert(0, os.path.dirname(__file__))
from ask_cortex_analyst import ask, CortexAnalystError

QUESTIONS_PATH = os.path.join(os.path.dirname(__file__), "..", "eval", "stress_test_questions.yaml")
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "..", "eval", "stress_test_cortex_results.yaml")

with open(QUESTIONS_PATH) as f:
    questions = yaml.safe_load(f)["questions"]

results = []
for q in questions:
    print(f"\n{'='*80}\n[{q['id']}] {q['question']}\n{'-'*80}")
    try:
        resp, _, latency = ask(q["question"])
    except CortexAnalystError as e:
        print(f"API ERROR: {e}")
        results.append({**q, "generated_sql": None, "cortex_text": f"API_ERROR: {e}", "latency": e.latency})
        continue

    sql_stmt, text = None, None
    for block in resp.get("message", {}).get("content", []):
        if block["type"] == "sql":
            sql_stmt = block["statement"]
        elif block["type"] == "text":
            text = block["text"]

    print(f"generated_sql: {'YES' if sql_stmt else 'none'}")
    if sql_stmt:
        print(sql_stmt)
    print(f"text: {text}")

    results.append({**q, "generated_sql": sql_stmt, "cortex_text": text, "latency": round(latency, 2)})

with open(RESULTS_PATH, "w") as f:
    yaml.dump({"results": results}, f, sort_keys=False, width=100, allow_unicode=True)
print(f"\nWrote results to {RESULTS_PATH}")
