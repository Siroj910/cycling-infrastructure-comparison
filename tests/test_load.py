"""Tests for loading collected runs into SQLite (issue #3). Fixture runs are made with a fake fetcher."""
import gzip, json, os

import pytest

from bikecollect import collect as K, config as C, db, load as Ld
from tests.test_collect import ok_fetcher

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def run_dir(tmp_path):
    out, _ = K.collect(C.ENDPOINTS[:1], root=str(tmp_path / "data"), pair_no=1, fetcher=ok_fetcher)
    return out


def count(conn, table, where="1=1", args=()):
    return conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", args).fetchone()[0]


def test_load_run_saves_snapshots_features_events_and_provenance(run_dir):
    conn = db.connect(":memory:")
    s = Ld.load_run(conn, run_dir)
    assert s["status"] == "loaded" and s["snapshots"] == 2 and s["features"] == 2 and not s["refused"]
    assert count(conn, "provenance") == 1 and count(conn, "sources") == 1
    snap = conn.execute("SELECT * FROM snapshots WHERE city = 'Amsterdam'").fetchone()
    assert snap["complete"] == 1 and snap["pair_valid"] == 0 and snap["query_text"].startswith("[out:json]")
    feat = conn.execute("SELECT * FROM source_features WHERE snapshot_id = ?", (snap["snapshot_id"],)).fetchone()
    assert feat["osm_way_id"] == 1 and feat["category"] and feat["length_m"] > 0
    # C1-C7 recorded as passed for each snapshot; P6 recorded as failed for the run
    assert count(conn, "quality_events", "check_name LIKE 'C%' AND passed = 1") == 14
    assert count(conn, "quality_events", "check_name = 'P6_coverage_500' AND passed = 0") == 1


def test_loading_the_same_run_twice_changes_nothing(run_dir):
    conn = db.connect(":memory:")
    Ld.load_run(conn, run_dir)
    before = [count(conn, t) for t in db.table_names(conn)]
    assert Ld.load_run(conn, run_dir)["status"] == "already_loaded"
    assert [count(conn, t) for t in db.table_names(conn)] == before


def test_raw_file_hash_mismatch_is_refused_and_logged(run_dir):
    with gzip.open(os.path.join(run_dir, "raw_Amsterdam_1.json.gz"), "wb") as fh:
        fh.write(b'{"elements": []}')                       # tampered raw file
    conn = db.connect(":memory:")
    s = Ld.load_run(conn, run_dir)
    assert len(s["refused"]) == 1 and "Amsterdam" in s["refused"][0]
    assert count(conn, "snapshots") == 1                     # Copenhagen still loaded
    ev = conn.execute("SELECT * FROM quality_events WHERE check_name = 'raw_hash_matches' AND passed = 0").fetchone()
    assert ev["severity"] == "error" and "not loaded" in ev["detail"]


def test_feasibility_and_non_assessed_runs_cannot_be_loaded(run_dir):
    conn = db.connect(":memory:")
    with pytest.raises(ValueError):
        Ld.load_run(conn, os.path.join(REPO, "feasibility", "20261026T142511Z"))
    p = os.path.join(run_dir, "provenance.json")
    prov = json.load(open(p))
    prov["purpose"] = "PRE-APPROVAL FEASIBILITY ONLY - not assessed data"
    json.dump(prov, open(p, "w"))
    with pytest.raises(ValueError):
        Ld.load_run(conn, run_dir)
    assert count(conn, "provenance") == 0
