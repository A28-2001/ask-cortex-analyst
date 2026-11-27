"""Defense in depth for executing model-generated SQL on a public app.

The real protection is the Snowflake role the app connects as, which is
read-only (see scripts/snowflake_cost_guardrails.sql). This is the second
layer: refuse to send anything but a single read statement, so a prompt that
talked the model into writing DML or DDL fails here rather than relying on
the grants alone. Cortex Analyst only ever generates SELECT statements, with
or without CTEs, so legitimate answers are never blocked.
"""

import re

_LINE_COMMENT = re.compile(r"--[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_STRING = re.compile(r"'(?:[^']|'')*'")
_WRITE_WORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|TRUNCATE|DROP|CREATE|ALTER|GRANT|REVOKE|"
    r"COPY|PUT|REMOVE|CALL|EXECUTE|USE|SET|UNSET|BEGIN|COMMIT|ROLLBACK)\b",
    re.IGNORECASE,
)


def is_read_only(sql: str) -> bool:
    """True for exactly one SELECT statement (CTEs allowed), nothing else."""
    if not sql:
        return False
    body = _BLOCK_COMMENT.sub(" ", _LINE_COMMENT.sub(" ", sql))
    # Ignore anything inside string literals: 'a; b' or 'DROP' as data is fine.
    body = _STRING.sub("''", body).strip().rstrip(";").strip()
    if ";" in body:
        return False  # more than one statement
    if not re.match(r"(SELECT|WITH)\b", body, re.IGNORECASE):
        return False
    return not _WRITE_WORDS.search(body)
