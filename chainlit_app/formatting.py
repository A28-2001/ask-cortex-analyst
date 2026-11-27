"""Answer formatting: humanized labels, formatted numbers, trimmed
boilerplate, a headline-stat treatment for single-value answers, a row cap
with a summary for long tables, and a chart for simple time series.

Pure functions with no Chainlit or network dependency, so they are unit
tested on their own (tests/test_formatting.py).

Number formats follow what the semantic model actually defines rather than
guessing from substrings: every *_pct measure is documented on a 0 to 100
scale, *_mrr facts are dollars, *_score and *_z_score are plain numbers, and
the rest are counts. When a column's meaning is ambiguous (a ratio Cortex
Analyst derived itself, say) it is shown as a plain number: an unlabelled
value is less polished, but a wrong unit is a wrong answer.
"""

import datetime as dt
import io
import math
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from difflib import SequenceMatcher

ACRONYMS = {"MRR", "ARR", "NRR", "ID", "SQL", "NPS", "CAC", "LTV", "SMB"}

# Matched against whole underscore-separated words of a column name, so
# CARRIER_COUNT isn't money because it contains ARR.
CURRENCY_WORDS = {"MRR", "ARR", "REVENUE", "COST", "PRICE", "AMOUNT"}
# A money word alongside one of these means a count, rate or score about
# money (CUSTOMERS_WITH_MRR, MRR_GROWTH_RATE, NET_MRR_Z_SCORE), not dollars.
NOT_MONEY_WORDS = {"COUNT", "CUSTOMER", "CUSTOMERS", "NUM", "NUMBER", "RATE", "RATIO",
                   "PCT", "PERCENT", "SCORE", "Z", "MONTHS", "DAYS", "SIZE"}
# Percentages whose 0 to 100 scale the semantic model documents. NRR is how
# Cortex Analyst tends to alias net_revenue_retention_pct.
KNOWN_PERCENT = ("RETENTION_RATE_PCT", "NET_REVENUE_RETENTION_PCT")
PERCENT_WORDS = {"NRR"}
PLAIN_INT_WORDS = {"YEAR", "QUARTER"}

PREAMBLE_RE = re.compile(r"^\s*This is our interpretation of your question:\s*", re.IGNORECASE)
DATE_TEXT = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[ T]00:00:00)?$")
LEADING_QUESTION = re.compile(r"^(?P<q>[^?\n]{3,300}\?)\s+(?P<rest>\S.*)$", re.DOTALL)
NOTE_LABEL = re.compile(r"^(?:note|nb)\s*:\s*", re.IGNORECASE)

INK = "#14181B"
BLUE = "#2438E0"


def _words(col: str):
    return set(col.upper().split("_"))


def humanize_column(name: str) -> str:
    """ENDING_MRR -> "Ending MRR", CUSTOMER_ID -> "Customer ID", RETENTION_RATE_PCT -> "Retention Rate %".

    A name that isn't an upper-case identifier was given as a quoted alias
    ("Total MRR"); it is already a display name, so it is left alone."""
    name = name.strip()
    if " " in name or any(c.islower() for c in name):
        return name
    words = []
    for part in name.split("_"):
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


def is_date_like(value) -> bool:
    return isinstance(value, (dt.date, dt.datetime)) or (isinstance(value, str) and bool(DATE_TEXT.match(value)))


def _kind(col: str) -> str:
    col = col.upper()
    words = _words(col)
    if col == "ID" or col.endswith("_ID"):
        return "id"
    if words & PLAIN_INT_WORDS:
        return "plain_int"
    if words & {"SCORE", "Z"}:
        return "number"
    if any(k in col for k in KNOWN_PERCENT) or words & PERCENT_WORDS:
        return "percent"
    if words & CURRENCY_WORDS and not words & NOT_MONEY_WORDS:
        return "currency"
    return "number"


def _decimal(value) -> Decimal:
    # repr() of a float is its shortest round-tripping form, so 2.675 becomes
    # Decimal("2.675") rather than 2.67499999999999982236431605997495353221893310546875.
    return value if isinstance(value, Decimal) else Decimal(repr(value) if isinstance(value, float) else value)


def format_value(col_name: str, value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, dt.datetime):
        return value.date().isoformat() if value.time() == dt.time() else value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, str):
        return value[:10] if DATE_TEXT.match(value) else value
    if not is_numeric(value):
        return str(value)

    kind = _kind(col_name)
    if kind == "id":
        return str(value)
    try:
        d = _decimal(value)
        if not d.is_finite():
            return "NaN" if d.is_nan() else ("∞" if d > 0 else "-∞")
        if kind == "plain_int" and d == d.to_integral_value():
            return str(int(d))
        if kind == "percent":
            return f"{d.quantize(Decimal('0.1'), ROUND_HALF_UP)}%"
        if kind == "currency":
            cents = d.quantize(Decimal("0.01"), ROUND_HALF_UP)
            return f"{'-' if cents < 0 else ''}${abs(cents):,.2f}"
        if d == d.to_integral_value():
            return f"{int(d):,}"
        return f"{d.quantize(Decimal('0.01'), ROUND_HALF_UP):,.2f}"
    except (InvalidOperation, ValueError, OverflowError):
        return str(value)  # never let a single odd value break the whole answer


def clean_interpretation_text(text: str, original_question: str) -> str:
    """Strip the "This is our interpretation of your question:" label from an
    interpretation, and drop the interpretation entirely if what remains is
    just a close paraphrase of the visitor's own question.

    Only interpretations (the text carrying that label) are filtered. A
    refusal or an explanation never carries it and is always kept whole, even
    if it happens to echo the question."""
    if not text:
        return ""
    if not PREAMBLE_RE.match(text):
        return text.strip()
    cleaned = PREAMBLE_RE.sub("", text, count=1).strip()
    similarity = SequenceMatcher(
        None, cleaned.lower().rstrip("?"), (original_question or "").lower().rstrip("?")
    ).ratio()
    if similarity > 0.72:
        return ""
    # It opened by repeating the question word for word, then added a note:
    # keep the note. A restatement that sharpens the question ("at the end of
    # December 2025") differs from it, and is kept as it is.
    m = LEADING_QUESTION.match(cleaned)
    if m and _same_words(m.group("q"), original_question):
        rest = m.group("rest").strip()
        if rest.startswith("(") and rest.endswith(")"):
            rest = rest[1:-1].strip()
        rest = NOTE_LABEL.sub("", rest, count=1)
        cleaned = rest[:1].upper() + rest[1:]
    return cleaned


def _same_words(a: str, b: str) -> bool:
    norm = lambda s: re.sub(r"\W+", " ", (s or "").lower()).strip()  # noqa: E731
    return SequenceMatcher(None, norm(a), norm(b)).ratio() >= 0.95


def _cell(text: str) -> str:
    # A literal | ends a markdown table cell and a newline ends the row, so
    # a value containing either would shift every column after it.
    return text.replace("|", "\\|").replace("\n", " ")


def rows_to_markdown(columns, rows, preview_limit: int = 10, total_rows=None) -> str:
    total = max(total_rows or 0, len(rows))
    headers = [_cell(humanize_column(c)) for c in columns]
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for row in rows[:preview_limit]:
        lines.append("| " + " | ".join(_cell(format_value(columns[i], v)) for i, v in enumerate(row)) + " |")
    table_md = "\n".join(lines)
    if total > preview_limit:
        table_md += f"\n\n**{total:,} total rows**, showing the first {preview_limit}."
    return table_md


def render_answer(columns, rows, total_rows=None) -> str:
    """Single row with exactly one numeric measure: feature it as a large
    headline stat with any other columns as small supporting context,
    instead of a one-row table. Everything else falls back to a table."""
    if len(rows) == 1 and (total_rows or 1) == 1:
        row = rows[0]
        numeric_idx = [i for i, v in enumerate(row) if is_numeric(v)]
        if len(numeric_idx) == 1:
            i = numeric_idx[0]
            md = f"## {format_value(columns[i], row[i])}\n_{humanize_column(columns[i])}_"
            context = [
                f"{humanize_column(columns[j])}: {format_value(columns[j], row[j])}"
                for j in range(len(columns))
                if j != i
            ]
            if context:
                md += "\n\n" + "  •  ".join(context)
            return md
    return rows_to_markdown(columns, rows, total_rows=total_rows)


def find_trend_columns(columns, rows):
    """(date column, value column) when the result is one simple time series,
    else None. Detected from the values, not the names: AVG_MONTHLY_MRR
    contains MONTH but isn't a date. Requires exactly one date column, exactly
    one numeric column, no text columns (a SEGMENT column means several series
    stacked together, which would draw as a sawtooth), one row per date, and
    at least three points."""
    if len(rows) < 3 or not columns:
        return None
    present = lambda i: [r[i] for r in rows if r[i] is not None]  # noqa: E731
    date_cols = [i for i in range(len(columns)) if present(i) and all(is_date_like(v) for v in present(i))]
    if len(date_cols) != 1:
        return None
    d = date_cols[0]
    others = [i for i in range(len(columns)) if i != d]
    if any(not is_numeric(v) for i in others for v in present(i)):
        return None
    numeric = [i for i in others if present(i)]
    if len(numeric) != 1 or len(present(numeric[0])) < 3:
        return None
    dates = [str(r[d]) for r in rows]
    if len(set(dates)) != len(dates):
        return None
    return d, numeric[0]


def trend_chart_png(columns, rows, date_idx, numeric_idx) -> bytes:
    """A small line chart for a time-trend result, as PNG bytes.

    Built with matplotlib's object-oriented Figure rather than pyplot: pyplot
    keeps every figure in a global registry (a leak in a long-running server)
    and isn't safe to drive from worker threads, which is where this runs so
    rendering never blocks other visitors' sessions. Transparent background
    so it sits on the chat's paper ground.
    """
    from matplotlib.figure import Figure  # imported lazily: slow, and only charts need it

    points = sorted(
        (format_value(columns[date_idx], r[date_idx]), float(r[numeric_idx]))
        for r in rows
        if r[date_idx] is not None and is_numeric(r[numeric_idx]) and math.isfinite(float(r[numeric_idx]))
    )
    fig = Figure(figsize=(6.5, 3), facecolor="none")
    ax = fig.subplots()
    ax.set_facecolor("none")
    ax.plot([p[0] for p in points], [p[1] for p in points], marker="o", markersize=4, color=BLUE, linewidth=2)
    ax.set_title(humanize_column(columns[numeric_idx]), fontsize=12, color=INK, loc="left")
    ax.tick_params(axis="x", rotation=45, labelsize=8, colors=INK)
    ax.tick_params(axis="y", labelsize=8, colors=INK)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, transparent=True)
    return buf.getvalue()
