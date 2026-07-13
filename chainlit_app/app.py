import os
import sys
import asyncio

import chainlit as cl
import snowflake.connector
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from ask_cortex_analyst import ask, CortexAnalystError  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def get_connection():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
        role=os.environ["SNOWFLAKE_ROLE"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.environ["SNOWFLAKE_SCHEMA"],
    )


def execute_sql(sql: str):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        columns = [c[0] for c in cur.description]
        rows = cur.fetchall()
        return columns, rows
    finally:
        conn.close()


def rows_to_markdown(columns, rows, limit=50):
    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    for row in rows[:limit]:
        lines.append("| " + " | ".join(str(v) for v in row) + " |")
    if len(rows) > limit:
        lines.append(f"\n_(showing first {limit} of {len(rows)} rows)_")
    return "\n".join(lines)


@cl.set_starters
async def starters():
    return [
        cl.Starter(
            label="Total MRR for a month",
            message="What was our total MRR in June 2026?",
        ),
        cl.Starter(
            label="Segment revenue trend",
            message="What drove the SMB revenue trend in Q3 2025?",
        ),
        cl.Starter(
            label="At-risk customers",
            message="Which customers are at risk?",
        ),
        cl.Starter(
            label="Guardrail check",
            message="Was churn anomalous in January 2025?",
        ),
    ]


@cl.on_chat_start
async def start():
    cl.user_session.set("history", None)


@cl.on_message
async def main(message: cl.Message):
    question = message.content
    history = cl.user_session.get("history")

    try:
        async with cl.Step(name="Cortex Analyst", type="tool") as step:
            step.input = question
            resp, new_history, latency = await asyncio.to_thread(ask, question, history)
            cl.user_session.set("history", new_history)

            sql_stmt, text = None, None
            for block in resp.get("message", {}).get("content", []):
                if block["type"] == "sql":
                    sql_stmt = block["statement"]
                elif block["type"] == "text":
                    text = block["text"]

            step.output = sql_stmt if sql_stmt else "(no SQL — question was out of scope or unanswerable)"
            if sql_stmt:
                step.language = "sql"
    except CortexAnalystError as e:
        await cl.Message(
            content=f"I couldn't reach Cortex Analyst just now ({e}). Try again in a moment."
        ).send()
        return

    # No SQL at all: a clean refusal (guardrail case) -- style it distinctly from a data answer.
    if not sql_stmt:
        await cl.Message(
            content="**Can't answer this** — " + (text or "I don't have enough information to answer that."),
        ).send()
        return

    try:
        columns, rows = await asyncio.to_thread(execute_sql, sql_stmt)
    except Exception as e:
        await cl.Message(
            content=f"The query I generated failed to run ({e}). Try rephrasing the question."
        ).send()
        return

    # Zero rows: never show a blank table. The interpretation text often already
    # explains why (semantic model instructions cover the known gaps) -- surface
    # it prominently instead of a silent empty result.
    if not rows:
        await cl.Message(
            content="**No matching data** — "
            + (text or "That query ran successfully but returned no matching data.")
        ).send()
        return

    table_md = rows_to_markdown(columns, rows)
    await cl.Message(content=f"{text}\n\n{table_md}").send()
