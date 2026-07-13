import os
import re
import time
import yaml
import snowflake.connector
from groq import Groq
from dotenv import load_dotenv
from schema_only import RAW_SCHEMA

load_dotenv()

MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = f"""You are a SQL assistant for a Snowflake database. You are given the
schema below. Write a SQL query to answer the user's question.

{RAW_SCHEMA}

Respond with ONLY a SQL query in a ```sql code block. If the question cannot be
answered using the tables and columns given above, respond with exactly:
CANNOT_ANSWER: <one sentence reason>
Do not explain the query, just return it (or the CANNOT_ANSWER line)."""

QUESTIONS_PATH = os.path.join(os.path.dirname(__file__), "..", "eval", "questions.yaml")
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "..", "eval", "baseline_results.yaml")

groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])

conn = snowflake.connector.connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    user=os.environ["SNOWFLAKE_USER"],
    private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
    role=os.environ["SNOWFLAKE_ROLE"],
    warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
    database=os.environ["SNOWFLAKE_DATABASE"],
    schema=os.environ["SNOWFLAKE_SCHEMA"],
)


def ask_baseline(question: str):
    start = time.time()
    resp = groq_client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        temperature=0,
    )
    latency = time.time() - start
    raw = resp.choices[0].message.content.strip()

    if "CANNOT_ANSWER" in raw:
        return None, raw, latency

    match = re.search(r"```sql\s*(.*?)```", raw, re.DOTALL | re.IGNORECASE)
    sql = match.group(1).strip() if match else raw.strip()
    return sql, raw, latency


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


def main():
    with open(QUESTIONS_PATH) as f:
        questions = yaml.safe_load(f)["questions"]

    results = []
    for i, q in enumerate(questions, 1):
        print(f"[{i}/{len(questions)}] {q['id']}: {q['question']}")
        sql, raw, latency = ask_baseline(q["question"])
        exec_result = execute_sql(sql) if sql else {"rows": None, "error": None}
        results.append({
            **q,
            "generated_sql": sql,
            "raw_response": raw,
            "actual_rows": exec_result["rows"],
            "exec_error": exec_result["error"],
            "latency": round(latency, 2),
        })
        status = "NO SQL (refused)" if not sql else ("SQL ERROR" if exec_result["error"] else "ran ok")
        print(f"    -> {status} ({latency:.2f}s)")
        time.sleep(0.3)

    with open(RESULTS_PATH, "w") as f:
        yaml.dump({"results": results}, f, sort_keys=False, width=100, allow_unicode=True)
    print(f"\nWrote {len(results)} raw baseline results to {RESULTS_PATH}")
    conn.close()


if __name__ == "__main__":
    main()
