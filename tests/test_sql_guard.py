"""Tests for chainlit_app/sql_guard.py: only a single read statement runs."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from chainlit_app import replay  # noqa: E402
from chainlit_app.sql_guard import is_read_only  # noqa: E402


@pytest.mark.parametrize(
    "entry_id,sql",
    [(e["id"], e["sql"]) for e in replay.entries() if e["kind"] == "data"],
)
def test_every_real_cortex_statement_is_allowed(entry_id, sql):
    # The guard must never block a legitimate answer: these are all the
    # statements Cortex Analyst actually generated during the evaluation.
    assert is_read_only(sql), entry_id


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM t WHERE note = 'please DROP it; now'",   # keywords inside a string are data
        "-- DROP TABLE x\nSELECT 1",                             # and inside comments
        "/* DELETE */ WITH a AS (SELECT 1) SELECT * FROM a",
        "select ending_mrr from mrr_movements;",
        "SELECT created_at, last_updated, offset_days FROM t",   # write words inside identifiers
    ],
)
def test_reads_are_allowed(sql):
    assert is_read_only(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE mrr_movements",
        "DELETE FROM mrr_movements",
        "UPDATE mrr_movements SET ending_mrr = 0",
        "INSERT INTO t VALUES (1)",
        "TRUNCATE TABLE t",
        "GRANT ALL ON SCHEMA analytics TO ROLE public",
        "CREATE TABLE t AS SELECT 1",
        "SELECT 1; DROP TABLE mrr_movements",                    # a second statement
        "WITH a AS (SELECT 1) DELETE FROM t",
        "USE ROLE ACCOUNTADMIN",
        "",
        None,
    ],
)
def test_anything_else_is_refused(sql):
    assert not is_read_only(sql)
