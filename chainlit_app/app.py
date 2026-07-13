import os
import sys
import asyncio

import chainlit as cl
import snowflake.connector
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from ask_cortex_analyst import ask, CortexAnalystError  # noqa: E402
from snowflake_auth import private_key_der  # noqa: E402
from formatting import (  # noqa: E402
    clean_interpretation_text,
    render_answer,
    find_trend_columns,
    build_trend_chart,
)

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def get_connection():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        private_key=private_key_der(),
        role=os.environ["SNOWFLAKE_ROLE"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.environ["SNOWFLAKE_SCHEMA"],
    )


def execute_sql(sql: str):
    """Reuses this session's one Snowflake connection instead of opening a
    fresh one per message. If the connection went stale (idle timeout, etc.)
    reconnect once and retry rather than failing the whole turn."""
    conn = cl.user_session.get("sf_conn")
    try:
        cur = conn.cursor()
        cur.execute(sql)
        columns = [c[0] for c in cur.description]
        rows = cur.fetchall()
        return columns, rows
    except snowflake.connector.errors.Error:
        conn = get_connection()
        cl.user_session.set("sf_conn", conn)
        cur = conn.cursor()
        cur.execute(sql)
        columns = [c[0] for c in cur.description]
        rows = cur.fetchall()
        return columns, rows


@cl.set_starters
async def starters():
    return [
        cl.Starter(label="Total MRR for a month", message="What was our total MRR in June 2026?"),
        cl.Starter(label="Segment revenue trend", message="What drove the SMB revenue trend in Q3 2025?"),
        cl.Starter(label="At-risk customers", message="Which customers are at risk?"),
        cl.Starter(label="Guardrail check", message="Was churn anomalous in January 2025?"),
    ]


@cl.on_chat_start
async def start():
    cl.user_session.set("history", None)
    conn = await asyncio.to_thread(get_connection)
    cl.user_session.set("sf_conn", conn)


@cl.on_chat_end
async def end():
    conn = cl.user_session.get("sf_conn")
    if conn:
        try:
            conn.close()
        except Exception:
            pass


@cl.action_callback("suggestion")
async def on_suggestion(action: cl.Action):
    question = action.payload.get("question", "")
    await cl.Message(content=question, type="user_message").send()
    await handle_question(question)


async def handle_question(question: str):
    history = cl.user_session.get("history")

    try:
        async with cl.Step(name="Cortex Analyst", type="tool") as step1:
            step1.input = question
            resp, new_history, latency = await asyncio.to_thread(ask, question, history)
            cl.user_session.set("history", new_history)

            sql_stmt, text, suggestions = None, None, []
            for block in resp.get("message", {}).get("content", []):
                if block["type"] == "sql":
                    sql_stmt = block["statement"]
                elif block["type"] == "text":
                    text = block["text"]
                elif block["type"] == "suggestions":
                    suggestions = block.get("suggestions", [])

            step1.output = sql_stmt if sql_stmt else "(no SQL — question was out of scope or unanswerable)"
            if sql_stmt:
                step1.language = "sql"
    except CortexAnalystError as e:
        await cl.Message(content=f"I couldn't reach Cortex Analyst just now ({e}). Try again in a moment.").send()
        return

    display_text = clean_interpretation_text(text, question)
    actions = [
        cl.Action(name="suggestion", label=s, payload={"question": s})
        for s in suggestions[:4]
    ]

    # No SQL at all: a clean refusal (guardrail case) -- style it distinctly from a data answer.
    if not sql_stmt:
        await cl.Message(
            content="**Can't answer this** — " + (display_text or "I don't have enough information to answer that."),
            actions=actions,
        ).send()
        return

    async with cl.Step(name="Running query on Snowflake", type="tool") as step2:
        step2.input = sql_stmt
        step2.language = "sql"
        try:
            columns, rows = await asyncio.to_thread(execute_sql, sql_stmt)
        except Exception as e:
            step2.output = f"failed: {e}"
            await cl.Message(content=f"The query I generated failed to run ({e}). Try rephrasing the question.").send()
            return
        step2.output = f"{len(rows)} row(s) returned"

    # Zero rows: never show a blank table. The interpretation text often already
    # explains why (semantic model instructions cover the known gaps) -- surface
    # it prominently instead of a silent empty result.
    if not rows:
        await cl.Message(
            content="**No matching data** — " + (display_text or "That query ran successfully but returned no matching data."),
            actions=actions,
        ).send()
        return

    answer_md = render_answer(columns, rows)
    content = f"{display_text}\n\n{answer_md}" if display_text else answer_md

    elements = []
    trend = find_trend_columns(columns, rows)
    if trend:
        fig = build_trend_chart(columns, rows, *trend)
        elements.append(cl.Pyplot(name="trend", figure=fig, display="inline"))

    await cl.Message(content=content, elements=elements, actions=actions).send()


@cl.on_message
async def main(message: cl.Message):
    await handle_question(message.content)
