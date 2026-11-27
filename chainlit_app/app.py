"""Chainlit glue for Ask Cortex Analyst.

What happens to every question:

1. If the live backend is believed to be up and the question is within the
   live budget, Cortex Analyst turns it into SQL and Snowflake runs it. The
   Snowflake connection opens on the first question that needs it, not when
   the page loads.
2. If either service is unavailable (the trial ended, the resource monitor
   suspended the warehouse at its monthly quota, an outage, no credentials),
   that is remembered for a few minutes and the recorded answer to that exact
   question is shown instead, labelled with the real reason. See replay.py.
3. With no recording for that question, the visitor is told why and offered
   the closest recorded questions to click.

Nothing slow runs in on_chat_start. Chainlit keeps the page's inputs disabled
until that handler returns, so connecting to Snowflake there meant a slow or
unreachable warehouse froze the whole page, with no explanation, for every
visitor.

How each outcome is worded and laid out lives in answers.py. Raw exception
text is logged, never shown.
"""

import asyncio
import datetime as dt
import logging
import os
import sys
import time

import chainlit as cl
import snowflake.connector
from chainlit.utils import utc_now
from dotenv import load_dotenv

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from ask_cortex_analyst import CortexAnalystError, ask  # noqa: E402
from snowflake_auth import private_key_der  # noqa: E402

from chainlit_app import answers, replay  # noqa: E402
from chainlit_app.formatting import trend_chart_png  # noqa: E402
from chainlit_app.sql_guard import is_read_only  # noqa: E402
from chainlit_app.starters import STARTER_GROUPS  # noqa: E402

load_dotenv(os.path.join(ROOT, ".env"))
log = logging.getLogger("ask_cortex_analyst")

# After an outage, skip the live path for this long. Long enough that a dead
# warehouse doesn't cost every visitor a failed round trip first, short
# enough that the live service comes back on its own.
BACKEND_RETRY_SECONDS = 300

# Cortex Analyst bills per message, serverless, which the warehouse resource
# monitor does not cap, and this page is public. Past these limits questions
# are answered from the recordings instead.
LIVE_DAILY_LIMIT = int(os.environ.get("LIVE_DAILY_LIMIT", "50"))
SESSION_WINDOW_SECONDS = 600
SESSION_WINDOW_LIMIT = int(os.environ.get("LIVE_SESSION_LIMIT", "10"))

# Cortex Analyst only needs recent turns to resolve a follow up ("now by
# segment"); capping keeps each request bounded. Must stay even so the
# history always starts with a user turn.
HISTORY_MESSAGES = 6

# Bounds on any single query, so one slow or huge result can't hold a worker
# thread for Snowflake's 2 day default timeout or exhaust the 512 MB host.
STATEMENT_TIMEOUT_SECONDS = 30
MAX_FETCH_ROWS = 1000

# Snowflake errors meaning the session expired rather than the SQL being bad.
SESSION_EXPIRED_ERRNOS = {390111, 390112, 390114}
# Failed to connect, no response, no active warehouse.
OUTAGE_ERRNOS = {250001, 250003, 606}
OUTAGE_MARKERS = ("trial has ended", "resource monitor", "cannot be resumed", "has been suspended")

_backend_down_until = 0.0
_daily_live = {"day": None, "count": 0}


class BackendUnavailable(Exception):
    """Cortex Analyst or Snowflake can't serve requests right now."""


def backend_available() -> bool:
    return time.monotonic() >= _backend_down_until


def mark_backend_down(reason: str) -> None:
    global _backend_down_until
    _backend_down_until = time.monotonic() + BACKEND_RETRY_SECONDS
    log.warning("Live backend unavailable, serving recorded answers for %ss: %s", BACKEND_RETRY_SECONDS, reason)


def is_cortex_outage(err: CortexAnalystError) -> bool:
    """No response at all, credentials or account rejected (an ended trial
    returns 401), rate limited, or a server error. Anything else means this
    particular request failed, not the service."""
    return err.status is None or err.status in (401, 403, 429) or err.status >= 500


def is_snowflake_outage(err: Exception) -> bool:
    return (
        getattr(err, "errno", None) in OUTAGE_ERRNOS
        or getattr(err, "sqlstate", None) == "57P03"
        or any(marker in str(err).lower() for marker in OUTAGE_MARKERS)
    )


def take_live_budget():
    """Reserve one live question. Returns None if allowed, else why not
    ("daily" or "session"). Runs only on the event loop, so no locking."""
    today = dt.date.today().isoformat()
    if _daily_live["day"] != today:
        _daily_live.update(day=today, count=0)
    if _daily_live["count"] >= LIVE_DAILY_LIMIT:
        return "daily"
    now = time.monotonic()
    recent = [t for t in (cl.user_session.get("live_times") or []) if now - t < SESSION_WINDOW_SECONDS]
    if len(recent) >= SESSION_WINDOW_LIMIT:
        return "session"
    cl.user_session.set("live_times", recent + [now])
    _daily_live["count"] += 1
    return None


# ---- Snowflake -----------------------------------------------------------

def connect():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        private_key=private_key_der(),
        role=os.environ["SNOWFLAKE_ROLE"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.environ["SNOWFLAKE_SCHEMA"],
        login_timeout=15,
        network_timeout=60,
        session_parameters={
            "STATEMENT_TIMEOUT_IN_SECONDS": STATEMENT_TIMEOUT_SECONDS,
            "STATEMENT_QUEUED_TIMEOUT_IN_SECONDS": STATEMENT_TIMEOUT_SECONDS,
            "MULTI_STATEMENT_COUNT": 1,
            "QUERY_TAG": "ask-cortex-analyst-demo",
        },
    )


def run_sql(conn, sql):
    """Execute one statement. Returns (columns, first rows, total row count)."""
    cur = conn.cursor()
    try:
        cur.execute(sql, timeout=STATEMENT_TIMEOUT_SECONDS)
        columns = [c[0] for c in cur.description]
        rows = cur.fetchmany(MAX_FETCH_ROWS)
        total = max(cur.rowcount or 0, len(rows))
        return columns, rows, total
    finally:
        cur.close()


async def close_quietly(conn):
    """conn.close() makes blocking HTTPS calls with retries, so never run it
    on the event loop, and never let a failed close break a turn."""
    if conn is None:
        return
    try:
        await asyncio.to_thread(conn.close)
    except Exception:
        log.debug("Closing a Snowflake connection failed", exc_info=True)


async def query(sql):
    """Run SQL on this session's connection, opening it on first use and
    reconnecting once if Snowflake expired the session. Raises
    BackendUnavailable when the warehouse can't serve queries at all; any
    other Snowflake error means the SQL itself failed."""
    conn = cl.user_session.get("sf_conn")
    for attempt in (1, 2):
        if conn is None or conn.is_closed():
            try:
                conn = await asyncio.to_thread(connect)
            except Exception as e:  # unreachable, suspended, or not configured
                raise BackendUnavailable(f"connect failed: {e}") from e
            cl.user_session.set("sf_conn", conn)
        try:
            return await asyncio.to_thread(run_sql, conn, sql)
        except snowflake.connector.errors.Error as e:
            if attempt == 1 and getattr(e, "errno", None) in SESSION_EXPIRED_ERRNOS:
                # Close the dead connection first: an unclosed one stays
                # registered with atexit for the life of the process.
                await close_quietly(conn)
                cl.user_session.set("sf_conn", None)
                conn = None
                continue
            if is_snowflake_outage(e):
                raise BackendUnavailable(f"query failed: {e}") from e
            raise


# ---- answering -----------------------------------------------------------

def suggestion_actions(questions):
    questions = [answers.without_dashes(q) for q in questions[:4]]
    return [cl.Action(name="suggestion", label=q, payload={"question": q}) for q in questions]


async def send_answer(question, text, sql, columns, rows, suggestions, total_rows=None, note=""):
    content, trend = answers.compose(question, text, sql, columns, rows, total_rows)
    elements = []
    if trend:
        try:
            png = await asyncio.to_thread(trend_chart_png, columns, rows, *trend)
            elements.append(cl.Image(name="trend", content=png, mime="image/png", display="inline"))
        except Exception:
            log.exception("Trend chart failed; sending the answer without it")
    await cl.Message(content=note + content, elements=elements, actions=suggestion_actions(suggestions)).send()


async def open_step(shown, name, **kwargs):
    """Show a running tool step and remember it in `shown`, so it can be
    withdrawn if the live backend turns out to be down."""
    step = cl.Step(name=name, type="tool", **kwargs)
    step.start = utc_now()
    await step.send()
    shown.append(step)
    return step


async def close_step(step, output, language=None):
    step.output = output
    if language:
        step.language = language
    step.end = utc_now()
    await step.update()


async def withdraw(shown, reason) -> bool:
    """The live backend is down. Take back the steps already on screen: the
    recorded answer that replaces them brings its own, and leaving a failed
    attempt above it would show the visitor the same step twice."""
    mark_backend_down(reason)
    for step in shown:
        try:
            await step.remove()
        except Exception:
            log.debug("Could not remove a withdrawn step", exc_info=True)
    return False


async def answer_live(question) -> bool:
    """Answer from Cortex Analyst and Snowflake. Returns False when the
    backend turns out to be unavailable, so the caller can fall back."""
    history = cl.user_session.get("history") or []
    shown = []
    step = await open_step(shown, "Cortex Analyst", show_input=False)
    try:
        resp, new_history, _ = await asyncio.to_thread(ask, question, history)
    except CortexAnalystError as e:
        log.warning("Cortex Analyst call failed (status %s): %s", e.status, e)
        if is_cortex_outage(e):
            return await withdraw(shown, f"Cortex Analyst returned {e.status}")
        await close_step(step, "The request failed.")
        await cl.Message(content=answers.REQUEST_FAILED).send()
        return True
    sql, text, suggestions = answers.parse_reply(resp)
    if sql or text:
        # Only a usable reply becomes context for follow ups.
        cl.user_session.set("history", new_history[-HISTORY_MESSAGES:])
    await close_step(step, sql or answers.NO_SQL_STEP, language="sql" if sql else None)

    columns = rows = total = None
    if sql:
        step = await open_step(shown, "Snowflake query", show_input="sql")
        step.input = sql
        if not is_read_only(sql):
            log.error("Refused to run SQL that is not a single read-only statement: %r", sql[:500])
            await close_step(step, "Not run: only read-only queries are allowed.")
            await cl.Message(content=answers.QUERY_FAILED).send()
            return True
        try:
            columns, rows, total = await query(sql)
        except BackendUnavailable as e:
            return await withdraw(shown, str(e))
        except Exception:
            log.exception("Generated SQL failed to run")
            await close_step(step, "The query failed.")
            await cl.Message(content=answers.QUERY_FAILED, actions=suggestion_actions(suggestions)).send()
            return True
        await close_step(step, f"{total:,} row{'' if total == 1 else 's'} returned")

    await send_answer(question, text, sql, columns, rows, suggestions, total_rows=total)
    return True


async def answer_recorded(question, reason="offline"):
    """Serve the recorded answer to exactly this question, or say plainly
    why there isn't a live one and offer the closest recorded questions."""
    entry = replay.lookup(question)
    if entry is None:
        await cl.Message(
            content=answers.no_recording(reason),
            actions=suggestion_actions(replay.suggest(question)),
        ).send()
        return
    async with cl.Step(name="Cortex Analyst", type="tool", show_input=False) as step:
        step.output = entry.get("sql") or answers.NO_SQL_STEP
        if entry.get("sql"):
            step.language = "sql"
    related = [q for q in replay.suggest(entry["question"], n=4) if replay.normalize(q) != entry["key"]]
    await send_answer(
        question, entry["text"], entry.get("sql"), entry.get("columns"), entry.get("rows"),
        related[:3], note=answers.recorded_note(entry, reason),
    )


async def handle_question(question):
    question = (question or "").strip()
    if not question:
        return
    # One turn at a time per session: a suggestion click and a typed question
    # would otherwise both read the same history and the last write would win.
    lock = cl.user_session.get("turn_lock")
    if lock is None:
        lock = asyncio.Lock()
        cl.user_session.set("turn_lock", lock)
    async with lock:
        try:
            reason = "offline"
            if backend_available():
                reason = take_live_budget()
                if reason is None:
                    if await answer_live(question):
                        return
                    reason = "offline"
            await answer_recorded(question, reason)
        except Exception:
            # Chainlit logs and swallows errors from on_message, which would
            # leave the visitor with no reply at all.
            log.exception("Unhandled error answering %r", question[:200])
            await cl.Message(content=answers.REQUEST_FAILED).send()


# ---- Chainlit hooks ------------------------------------------------------

@cl.set_starter_categories
async def starter_categories():
    return [
        cl.StarterCategory(
            label=group,
            starters=[cl.Starter(label=label, message=message) for label, message in starters],
        )
        for group, starters in STARTER_GROUPS
    ]


@cl.on_chat_start
async def start():
    # Deliberately does nothing slow; see the module docstring.
    cl.user_session.set("history", [])


@cl.on_chat_end
async def end():
    await close_quietly(cl.user_session.get("sf_conn"))


@cl.action_callback("suggestion")
async def on_suggestion(action: cl.Action):
    question = (action.payload or {}).get("question", "")
    await action.remove()
    await cl.Message(content=question, type="user_message").send()
    await handle_question(question)


@cl.on_message
async def main(message: cl.Message):
    await handle_question(message.content)
