from datetime import datetime, timedelta, timezone

from bikecollect.checks import completeness, fresh, pair_checks

T0 = datetime(2026, 10, 23, 8, 0, tzinfo=timezone.utc)


def response(n_ways=2, count=None, remark=None, ts="2026-10-23T07:58:00Z", broken=False):
    ways = []
    for i in range(n_ways):
        geom = [{"lat": 52.37, "lon": 4.89}, {"lat": 52.371, "lon": 4.891}]
        ways.append({"type": "way", "id": i, "nodes": [10 * i, 10 * i + 1],
                     "geometry": geom[:1] if broken else geom, "tags": {"highway": "cycleway"}})
    js = {"osm3s": {"timestamp_osm_base": ts},
          "elements": [{"type": "count", "tags": {"ways": str(n_ways if count is None else count)}}] + ways}
    if remark:
        js["remark"] = remark
    return js


BBOX = (52.3, 4.8, 52.4, 4.9)


def test_complete_response_passes_all():
    assert all(completeness(200, response(), BBOX).values())


def test_truncated_response_fails_count_check():
    assert not completeness(200, response(count=5), BBOX)["C5_count_matches"]


def test_runtime_remark_fails():
    r = completeness(200, response(remark="runtime error: Query timed out"), BBOX)
    assert not r["C3_no_runtime_remark"]


def test_missing_geometry_fails_structure():
    assert not completeness(200, response(broken=True), BBOX)["C6_way_structure"]


def test_http_error_fails():
    r = completeness(504, None, BBOX)
    assert not r["C1_http_200"] and not any(r.values())


def test_freshness_boundary_72h():
    assert fresh(T0, T0 - timedelta(hours=72))
    assert not fresh(T0, T0 - timedelta(hours=72, minutes=1))
    assert not fresh(T0, None)


def _rec(endpoint, src, segs=600):
    return {"endpoint": endpoint, "request_utc": T0, "response_utc": T0 + timedelta(minutes=2),
            "source_ts": src, "completeness": {"c": True}, "core_segments_lower": segs}


def test_valid_pair():
    a = _rec("x", T0 - timedelta(minutes=3))
    b = _rec("x", T0 - timedelta(minutes=2))
    assert pair_checks(a, b)["PAIR_VALID"]


def test_stale_pair_like_feasibility_run_fails():
    a = _rec("x", datetime(2026, 7, 24, tzinfo=timezone.utc))
    b = _rec("x", datetime(2026, 5, 31, tzinfo=timezone.utc))
    r = pair_checks(a, b)
    assert not r["P3_both_fresh_72h"] and not r["P4_source_gap_24h"] and not r["PAIR_VALID"]


def test_mixed_endpoints_fail():
    r = pair_checks(_rec("x", T0), _rec("y", T0))
    assert not r["P1_same_endpoint"] and not r["PAIR_VALID"]


def test_coverage_below_500_fails():
    r = pair_checks(_rec("x", T0, segs=499), _rec("x", T0))
    assert not r["P6_coverage_500"]
