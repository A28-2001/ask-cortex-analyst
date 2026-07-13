"""Answer formatting: humanized labels, formatted numbers, trimmed
boilerplate, a headline-stat treatment for single-value answers, and a
row cap with a summary for long tables. Pure functions, no Chainlit or
network dependency, so they're unit-testable on their own."""

import re
from decimal import Decimal
from difflib import SequenceMatcher

ACRONYMS = {"MRR", "NRR", "ID", "SQL", "NPS", "CAC", "LTV", "SMB"}
CURRENCY_HINTS = ("MRR", "ARR", "REVENUE", "COST", "PRICE", "AMOUNT")
PERCENT_HINTS = ("PCT", "PERCENT", "RETENTION_RATE")
PREAMBLE_RE = re.compile(r"^This is our interpretation of your question:\s*\n+", re.IGNORECASE)


def humanize_column(name: str) -> str:
    """ENDING_MRR -> "Ending MRR", CUSTOMER_ID -> "Customer ID", CHURN_RATE_PCT -> "Churn Rate %"."""
    words = []
    for part in name.strip().split("_"):
        upper = part.upper()
        if upper == "PCT":
            words.append("%")
        elif upper in ACRONYMS:
            words.append(upper)
        elif part.isdigit():
            words.append(part)
        else:
            words.append(part.capitalize())
    return " ".join(words)


def is_numeric(value) -> bool:
    return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)


def format_value(col_name: str, value) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    col_upper = col_name.upper()
    if is_numeric(value):
        if col_upper.endswith("_ID") or col_upper == "ID":
            return str(value)
        num = float(value)
        if any(h in col_upper for h in PERCENT_HINTS):
            return f"{num:.1f}%"
        if any(h in col_upper for h in CURRENCY_HINTS):
            return f"${num:,.2f}"
        if num == int(num):
            return f"{int(num):,}"
        return f"{num:,.2f}"
    return str(value)


def clean_interpretation_text(text: str, original_question: str) -> str:
    """Strip the "This is our interpretation of your question:" boilerplate label,
    and drop the remaining text entirely if it's just a close paraphrase of the
    user's own question -- that adds no information. Keeps genuine elaboration
    (e.g. a multi-part clarification) and leaves guardrail refusal text untouched
    (it never matches the preamble pattern in the first place)."""
    if not text:
        return ""
    cleaned = PREAMBLE_RE.sub("", text).strip()
    similarity = SequenceMatcher(
        None, cleaned.lower().rstrip("?"), original_question.lower().rstrip("?")
    ).ratio()
    if similarity > 0.72:
        return ""
    return cleaned


def rows_to_markdown(columns, rows, preview_limit: int = 10) -> str:
    headers = [humanize_column(c) for c in columns]
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for row in rows[:preview_limit]:
        formatted = [format_value(columns[i], v) for i, v in enumerate(row)]
        lines.append("| " + " | ".join(formatted) + " |")
    table_md = "\n".join(lines)
    if len(rows) > preview_limit:
        table_md += f"\n\n**{len(rows)} total rows** — showing the first {preview_limit}."
    return table_md


def render_answer(columns, rows) -> str:
    """Single row with exactly one numeric measure: feature it as a large
    headline stat with any other columns as small supporting context,
    instead of a one-row table. Everything else falls back to a table."""
    if len(rows) == 1:
        row = rows[0]
        numeric_idx = [i for i, v in enumerate(row) if is_numeric(v)]
        if len(numeric_idx) == 1:
            i = numeric_idx[0]
            headline_value = format_value(columns[i], row[i])
            headline_label = humanize_column(columns[i])
            context = [
                f"{humanize_column(columns[j])}: {format_value(columns[j], row[j])}"
                for j in range(len(columns))
                if j != i
            ]
            md = f"## {headline_value}\n_{headline_label}_"
            if context:
                md += "\n\n" + "  •  ".join(context)
            return md
    return rows_to_markdown(columns, rows)


def build_trend_chart(columns, rows, date_idx, numeric_idx):
    """A small line chart for a time-trend result. Returns a matplotlib Figure."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    x = [str(r[date_idx]) for r in rows]
    y = [float(r[numeric_idx]) for r in rows]
    fig, ax = plt.subplots(figsize=(6.5, 3))
    ax.plot(x, y, marker="o", color="#14B8A6", linewidth=2)
    ax.set_title(humanize_column(columns[numeric_idx]), fontsize=12)
    ax.tick_params(axis="x", rotation=45, labelsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    return fig


def find_trend_columns(columns, rows):
    """Return (date_col_index, numeric_col_index) if this result looks like a
    time trend (a date/month column + exactly one numeric measure, 3+ rows),
    else None."""
    if len(rows) < 3:
        return None
    date_idx, numeric_idx = None, None
    numeric_count = 0
    for i, c in enumerate(columns):
        if date_idx is None and ("MONTH" in c.upper() or "DATE" in c.upper()):
            date_idx = i
        elif is_numeric(rows[0][i]):
            numeric_count += 1
            numeric_idx = i
    if date_idx is not None and numeric_count == 1:
        return date_idx, numeric_idx
    return None
