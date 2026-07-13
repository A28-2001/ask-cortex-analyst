import os
import sys
import time
import yaml
import snowflake.connector
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
from ask_cortex_analyst import ask, CortexAnalystError

load_dotenv()

RESULTS_PATH = os.path.join(os.path.dirname(__file__), "..", "eval", "holdout_results.yaml")

conn = snowflake.connector.connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    user=os.environ["SNOWFLAKE_USER"],
    private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
    role=os.environ["SNOWFLAKE_ROLE"],
    warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
    database=os.environ["SNOWFLAKE_DATABASE"],
    schema=os.environ["SNOWFLAKE_SCHEMA"],
)

# Fresh questions, never used to test or tune the semantic model.
# H7/H8 deliberately probe generalization of the two behavioral fixes with
# DIFFERENT literal values than the ones used to diagnose/fix them.
ANSWERABLE = [
    dict(id="h1", category="point_in_time", question="What was our ending MRR in August 2025?",
         sql="SELECT ending_mrr FROM mrr_movements WHERE month = '2025-08-01'"),
    dict(id="h2", category="period_aggregation", question="How much new MRR did we add in the first half of 2025?",
         sql="SELECT SUM(new_mrr) FROM mrr_movements WHERE month BETWEEN '2025-01-01' AND '2025-06-30'"),
    dict(id="h3", category="segment", question="What was the SMB segment's net revenue retention in October 2025?",
         sql="SELECT net_revenue_retention_pct FROM mrr_movements_by_segment WHERE segment = 'smb' AND month = '2025-10-01'"),
    dict(id="h4", category="cohort_retention", question="What percentage of the June 2025 cohort was still active after 4 months?",
         sql="SELECT retention_rate_pct FROM cohort_retention WHERE cohort_month = '2025-06-01' AND months_since_cohort = 4"),
    dict(id="h5", category="anomaly", question="In months flagged as anomalous during 2025, what was the average net revenue retention?",
         sql="""SELECT ROUND(AVG(m.net_revenue_retention_pct), 1) FROM mrr_movements m
                JOIN anomaly_flags a ON m.month = a.month
                WHERE a.anomaly_status = 'flagged' AND a.month BETWEEN '2025-01-01' AND '2025-12-31'"""),
    dict(id="h6", category="ambiguous", question="How much did our MRR grow in the first quarter of 2026?",
         sql="""SELECT (SELECT ending_mrr FROM mrr_movements WHERE month = '2026-03-01')
                       - (SELECT starting_mrr FROM mrr_movements WHERE month = '2026-01-01')"""),
]

GUARDRAIL = [
    dict(id="h7", category="guardrail_nonexistent_entity", question="What is the health score for customer CUST-0777?",
         expected_reason="CUST-0777 is outside the valid range CUST-0001 to CUST-0500 (a different literal than the CUST-9999 used to diagnose/fix this behavior -- tests generalization)."),
    dict(id="h8", category="guardrail_undefined_metric", question="What is our gross margin?",
         expected_reason="No cost-of-goods-sold or margin data exists in this dataset -- a completely new undefined-metric case, not one of the original 6 guardrail questions."),
]


def fetch_ground_truth(sql):
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    cur.close()
    if len(rows) == 1 and len(rows[0]) == 1:
        return str(rows[0][0])
    return str(rows)


def extract_blocks(result):
    sql_stmt, text = None, None
    for block in result.get("message", {}).get("content", []):
        if block["type"] == "sql":
            sql_stmt = block["statement"]
        elif block["type"] == "text":
            text = block["text"]
    return sql_stmt, text


def execute_sql(sql):
    cur = conn.cursor()
    try:
        cur.execute(sql)
        return {"rows": [list(r) for r in cur.fetchall()], "error": None}
    except Exception as e:
        return {"rows": None, "error": str(e)}
    finally:
        cur.close()


results = []

for q in ANSWERABLE:
    truth = fetch_ground_truth(q["sql"])
    print(f"[{q['id']}] {q['question']}\n    ground truth: {truth}")
    try:
        resp, _, latency = ask(q["question"])
    except CortexAnalystError as e:
        results.append({**q, "type": "answerable", "ground_truth_value": truth, "error": str(e), "score": 0.0, "verdict": "api_error"})
        continue
    sql_stmt, text = extract_blocks(resp)
    exec_result = execute_sql(sql_stmt) if sql_stmt else {"rows": None, "error": None}
    print(f"    generated_sql: {'yes' if sql_stmt else 'NO SQL (refused)'}")
    print(f"    actual_rows: {exec_result['rows']}")
    results.append({
        **q, "type": "answerable", "ground_truth_value": truth,
        "generated_sql": sql_stmt, "cortex_text": text,
        "actual_rows": exec_result["rows"], "exec_error": exec_result["error"],
        "latency": round(latency, 2),
    })
    time.sleep(0.5)

for q in GUARDRAIL:
    print(f"[{q['id']}] {q['question']}")
    try:
        resp, _, latency = ask(q["question"])
    except CortexAnalystError as e:
        results.append({**q, "type": "guardrail", "error": str(e), "score": 0.0, "verdict": "api_error"})
        continue
    sql_stmt, text = extract_blocks(resp)
    print(f"    generated_sql: {'yes' if sql_stmt else 'NO SQL (refused)'}")
    print(f"    text: {text}")
    results.append({**q, "type": "guardrail", "generated_sql": sql_stmt, "cortex_text": text, "latency": round(latency, 2)})
    time.sleep(0.5)

with open(RESULTS_PATH, "w") as f:
    yaml.dump({"results": results}, f, sort_keys=False, width=100, allow_unicode=True)

print(f"\nWrote raw holdout results to {RESULTS_PATH}")
conn.close()
