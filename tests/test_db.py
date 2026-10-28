"""Tests for the SQLite schema (issue #2)."""
import sqlite3

import pytest

from bikecollect import db


def test_schema_creates_five_tables_and_is_idempotent(tmp_path):
    path = str(tmp_path / "data" / "t.sqlite")
    conn = db.connect(path)
    expected = ["provenance", "quality_events", "snapshots", "source_features", "sources"]
    assert db.table_names(conn) == expected
    conn.close()
    conn = db.connect(path)                     # second open: no error, nothing duplicated
    assert db.table_names(conn) == expected
    assert conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION


def test_foreign_keys_and_checks_are_enforced():
    conn = db.connect(":memory:")
    with pytest.raises(sqlite3.IntegrityError):  # snapshot pointing at a run that does not exist
        conn.execute("""INSERT INTO snapshots (snapshot_id, run_id, source_id, city, service_no, pair_valid,
                        complete, query_text, query_sha256, raw_file, response_sha256, envelope_swne)
                        VALUES ('x', 'no-such-run', 1, 'Amsterdam', 1, 1, 1, 'q', 'h', 'f', 'h', '[]')""")
    conn.execute("INSERT INTO sources (source_id, endpoint) VALUES (1, 'https://example/api')")
    conn.execute("""INSERT INTO provenance VALUES ('r', 'p', 1, 'a', 's', 'f', 1, NULL, 'c', 0, '{}', '[]', 'h', 'l')""")
    conn.execute("""INSERT INTO snapshots (snapshot_id, run_id, source_id, city, service_no, pair_valid,
                    complete, query_text, query_sha256, raw_file, response_sha256, envelope_swne)
                    VALUES ('s', 'r', 1, 'Amsterdam', 1, 1, 1, 'q', 'h', 'f', 'h', '[]')""")
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):  # protection must be P, U, X or NULL
        conn.execute("""INSERT INTO source_features VALUES ('s', 1, 0, 'road_lane', NULL, 'Z', 1, 1, '', 'primary',
                        1.0, 1.0, '{}', '[]', '[]')""")
