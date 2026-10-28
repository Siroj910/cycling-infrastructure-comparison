"""Tests for the assessed `collect` command (issue #1). No network: a fake fetcher stands in for Overpass."""
import gzip, hashlib, json, os
from datetime import timedelta

import pytest

from bikecollect import collect as K
from bikecollect import config as C
from bikecollect.feasibility_pair import now, iso


def fake_response(city):
    """A small, structurally complete Overpass response: one cycleway at the city centre."""
    c = C.CITIES[city]
    lat, lon = c["lat"], c["lon"]
    geom = [{"lat": lat, "lon": lon}, {"lat": lat + 0.001, "lon": lon + 0.001}]
    return {
        "osm3s": {"timestamp_osm_base": iso(now() - timedelta(hours=1))},
        "elements": [
            {"type": "count", "id": 0, "tags": {"ways": "1"}},
            {"type": "way", "id": 1, "nodes": [10, 11], "geometry": geom, "tags": {"highway": "cycleway"}},
        ],
    }


def ok_fetcher(endpoint, query, log):
    # identify the city from the envelope in the query (Amsterdam ~52 N, Copenhagen ~55 N)
    city = "Amsterdam" if "(52." in query else "Copenhagen"
    raw = json.dumps(fake_response(city)).encode()
    t0 = now()
    log.append({"endpoint": endpoint, "attempt": 1, "request_utc": iso(t0), "status": 200,
                "bytes": len(raw), "response_utc": iso(now()), "sha256": hashlib.sha256(raw).hexdigest()})
    return 200, raw, t0, now()


def failing_fetcher(endpoint, query, log):
    log.append({"endpoint": endpoint, "attempt": 1, "request_utc": iso(now()),
                "error": "ConnectTimeout: simulated", "response_utc": iso(now())})
    return None, None, None, None


def test_refuses_to_write_under_feasibility(tmp_path):
    target = tmp_path / "feasibility" / "x"
    with pytest.raises(ValueError):
        K.collect(C.ENDPOINTS, root=str(target), fetcher=ok_fetcher)
    assert not target.exists()


def test_writes_snapshot_and_provenance_to_data(tmp_path):
    root = tmp_path / "data"
    out, prov = K.collect(C.ENDPOINTS[:1], root=str(root), pair_no=1, fetcher=ok_fetcher)
    assert os.path.dirname(out) == str(root)
    files = set(os.listdir(out))
    assert {"provenance.json", "report.md", "raw_Amsterdam_1.json.gz", "raw_Copenhagen_1.json.gz"} <= files

    saved = json.load(open(os.path.join(out, "provenance.json")))
    assert saved["purpose"] == "ASSESSED POST-APPROVAL COLLECTION"
    assert saved["pair_no"] == 1 and "git_commit" in saved["code"]
    for city, rec in saved["pairs_tried"][0]["cities"].items():
        # full query kept, and its hash matches
        assert rec["query"].startswith("[out:json]")
        assert rec["query_sha256"] == hashlib.sha256(rec["query"].encode()).hexdigest()
        # raw file on disk matches the recorded response hash
        raw = gzip.open(os.path.join(out, rec["raw_file"])).read()
        assert rec["response_sha256"] == hashlib.sha256(raw).hexdigest()
        assert rec["request_utc"] and rec["response_utc"] and rec["source_ts"]
        assert all(rec["completeness"].values())
    # one way per city is far below 500 core segments, so P6 fails and the pair is not valid
    pc = saved["pairs_tried"][0]["pair_checks"]
    assert pc["P6_coverage_500"] is False and saved["pair_valid"] is False


def test_failed_pair_is_logged_and_exit_code_nonzero(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(K, "fetch", failing_fetcher)
    assert K.main(["--pair", "1"]) == 1
    (run_dir,) = os.listdir(tmp_path / "data")
    prov = json.load(open(tmp_path / "data" / run_dir / "provenance.json"))
    # every service in the fixed order was tried, and every failure was recorded
    assert [p["endpoint"] for p in prov["pairs_tried"]] == C.ENDPOINTS
    assert len(prov["request_log"]) == len(C.ENDPOINTS)
    assert all("error" in r for r in prov["request_log"])
    assert prov["pair_valid"] is False
