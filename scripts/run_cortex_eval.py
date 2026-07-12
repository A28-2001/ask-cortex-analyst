import os
import sys
import time
import yaml
import snowflake.connector
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
from ask_cortex_analyst import ask, CortexAnalystError

load_dotenv()

QUESTIONS_PATH = os.path.join(os.path.dirname(__file__), "..", "eval", "questions.yaml")
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "..", "eval", "cortex_analyst_results.yaml")

conn = snowflake.connector.connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    user=os.environ["SNOWFLAKE_USER"],
    private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
    role=os.environ["SNOWFLAKE_ROLE"],
    warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
    database=os.environ["SNOWFLAKE_DATABASE"],
    schema=os.environ["SNOWFLAKE_SCHEMA"],
)


def execute_sql(sql: str):
    cur = conn.cursor()
    try:
        cur.execute(sql)
        rows = cur.fetchall()
        return {"rows": [list(r) for r in rows], "error": None}
    except Exception as e:
        return {"rows": None, "error": str(e)}
    finally:
        cur.close()


def extract_blocks(result: dict):
    sql_stmt, text = None, None
    for block in result.get("message", {}).get("content", []):
        if block["type"] == "sql":
            sql_stmt = block["statement"]
        elif block["type"] == "text":
            text = block["text"]
    return sql_stmt, text


def try_auto_score(q: dict, sql_stmt, text, exec_result) -> dict:
    """Best-effort automated verdict. Anything not clearly resolvable is left
    as needs_review for manual scoring against the frozen rubric."""
    if q["type"] == "answerable":
        if sql_stmt is None:
            return {"verdict": "over_refused", "score": 0.5, "auto": True,
                     "reason": "Cortex Analyst refused a question that has a real answer."}
        if exec_result["error"]:
            return {"verdict": "incorrect", "score": 0.0, "auto": True,
                     "reason": f"Generated SQL failed to execute: {exec_result['error']}"}
        rows = exec_result["rows"]
        truth = q["ground_truth_value"]
        if rows and len(rows) == 1 and len(rows[0]) == 1:
            actual = rows[0][0]
            try:
                truth_f, actual_f = float(truth), float(actual)
                tol = max(abs(truth_f) * 0.005, 0.5)
                if abs(truth_f - actual_f) <= tol:
                    return {"verdict": "correct", "score": 1.0, "auto": True, "reason": "Numeric match within tolerance."}
                else:
                    return {"verdict": "needs_review", "score": None, "auto": False,
                             "reason": f"Numeric mismatch: got {actual}, expected {truth}."}
            except (ValueError, TypeError):
                if str(actual).strip().lower() == str(truth).strip().lower():
                    return {"verdict": "correct", "score": 1.0, "auto": True, "reason": "Exact string match."}
                return {"verdict": "needs_review", "score": None, "auto": False,
                         "reason": f"Non-numeric mismatch: got {actual!r}, expected {truth!r}."}
        return {"verdict": "needs_review", "score": None, "auto": False,
                 "reason": f"Multi-row/multi-column result ({len(rows) if rows else 0} rows) — needs manual comparison against ground truth."}
    else:  # guardrail
        if sql_stmt is None:
            return {"verdict": "correctly_refused", "score": 1.0, "auto": True,
                     "reason": "No SQL generated; refused with explanation."}
        return {"verdict": "needs_review", "score": None, "auto": False,
                 "reason": "Cortex Analyst generated SQL for a guardrail question — check whether it hallucinated or produced a defensible empty/zero result."}


def main():
    with open(QUESTIONS_PATH) as f:
        questions = yaml.safe_load(f)["questions"]

    results = []
    for i, q in enumerate(questions, 1):
        print(f"[{i}/{len(questions)}] {q['id']}: {q['question']}")
        try:
            resp, _, latency = ask(q["question"])
        except CortexAnalystError as e:
            results.append({**q, "error": str(e), "latency": e.latency, "verdict": "api_error", "score": 0.0})
            print(f"    API ERROR: {e}")
            time.sleep(1)
            continue

        sql_stmt, text = extract_blocks(resp)
        exec_result = execute_sql(sql_stmt) if sql_stmt else {"rows": None, "error": None}
        verdict = try_auto_score(q, sql_stmt, text, exec_result)

        results.append({
            **q,
            "generated_sql": sql_stmt,
            "cortex_text": text,
            "actual_rows": exec_result["rows"],
            "exec_error": exec_result["error"],
            "latency": round(latency, 2),
            **verdict,
        })
        print(f"    -> {verdict['verdict']} ({latency:.2f}s)")
        time.sleep(0.5)  # light rate-limit courtesy

    with open(RESULTS_PATH, "w") as f:
        yaml.dump({"results": results}, f, sort_keys=False, width=100, allow_unicode=True)

    needs_review = [r for r in results if r["verdict"] == "needs_review"]
    print(f"\nWrote {len(results)} results to {RESULTS_PATH}")
    print(f"{len(needs_review)} question(s) need manual review: {[r['id'] for r in needs_review]}")

    conn.close()


if __name__ == "__main__":
    main()
