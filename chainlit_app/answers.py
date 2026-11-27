"""How every kind of outcome is worded and laid out for the visitor.

Pure functions, no Chainlit and no network. app.py decides which outcome
happened; this module decides what the visitor reads. Keeping it here means
the live path and the recorded path render identically, and every branch is
unit tested.

House rules for this copy: plain sentences, no em or en dashes, and never
show raw exception text (it leaks internals and reads as broken).
"""

import re

from chainlit_app.formatting import (
    clean_interpretation_text,
    find_trend_columns,
    render_answer,
)

SPACED_DASH = re.compile(r"\s+[\u2013\u2014]\s+")
RANGE_DASH = re.compile(r"(?<=\w)\u2013(?=\w)")
ANY_DASH = re.compile(r"\s*[\u2013\u2014]\s*")

DECLINED_DEFAULT = "That question is outside what this data can answer."
EMPTY_DEFAULT = "The query ran, but no rows matched."

NO_SQL_STEP = "No SQL generated. The question was declined."

# Why a question was answered from the recordings instead of live. The visitor
# is always told the real reason.
WHY_RECORDED = {
    "offline": "The live warehouse is offline",
    "daily": "This public demo caps live questions per day, and today's are used up",
    "session": "Live answers are rate limited per visitor, and you've reached the limit for a few minutes",
}


def no_recording(reason="offline"):
    return (
        f"**{WHY_RECORDED[reason]},** so I can only replay answers recorded during the "
        "evaluation, and I don't have one for that exact question. These are the closest "
        "ones I do have:"
    )

QUERY_FAILED = (
    "**That query didn't run.** Snowflake rejected the SQL that was generated for "
    "this one. Try rephrasing it, or pick one of the starters."
)

REQUEST_FAILED = (
    "**Something went wrong reaching the analyst.** Give it a moment and try "
    "again, or pick one of the starters."
)


def without_dashes(text: str) -> str:
    """The house style has no em or en dashes on screen, and that includes
    the model's own prose. A spaced dash becomes a comma ("data, but none of
    these"), and an en dash range becomes "to" ("July to September")."""
    if not text:
        return text
    text = SPACED_DASH.sub(", ", text)
    text = RANGE_DASH.sub(" to ", text)
    return ANY_DASH.sub(", ", text)


def parse_reply(resp):
    """Pull (sql, interpretation text, suggested follow ups) out of a Cortex
    Analyst response. Tolerates missing or oddly shaped blocks rather than
    crashing mid-answer on a KeyError."""
    sql, text, suggestions = None, "", []
    for block in ((resp or {}).get("message") or {}).get("content") or []:
        kind = (block or {}).get("type")
        if kind == "sql":
            sql = block.get("statement") or None
        elif kind == "text":
            text = block.get("text") or ""
        elif kind == "suggestions":
            suggestions = [s for s in (block.get("suggestions") or []) if isinstance(s, str) and s.strip()]
    return sql, text, suggestions


def compose(question, text, sql, columns=None, rows=None, total_rows=None):
    """The markdown body for an answer, plus a (date, value) column pair to
    chart when the result is a simple time series, else None. `total_rows`
    is the full result size when only the first rows were fetched."""
    display = without_dashes(clean_interpretation_text(text, question))
    if not sql:
        return f"**Can't answer this.** {display or DECLINED_DEFAULT}", None
    if not rows:
        return f"**No matching data.** {display or EMPTY_DEFAULT}", None
    body = render_answer(columns, rows, total_rows=total_rows)
    return (f"{display}\n\n{body}" if display else body), find_trend_columns(columns, rows)


def recorded_note(entry, reason="offline"):
    """The label on every replayed answer, so nobody mistakes it for live."""
    note = (
        f"> **Recorded answer.** {WHY_RECORDED[reason]}, so this is the real response "
        f"captured during {entry['origin']} in {entry['recorded']}."
    )
    if entry["kind"] == "data":
        note += " The result is what Snowflake returned at the time."
    return note + "\n\n"
