"""Completeness, freshness and pairing checks (pure functions, unit-tested)."""
from datetime import datetime, timezone
from typing import Dict, List, Optional

from . import config as C


def parse_ts(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def completeness(status: int, js: Optional[dict], bbox=None) -> Dict[str, bool]:
    """C1-C7 for one city response. bbox = (S, W, N, E)."""
    r = {}
    r["C1_http_200"] = status == 200
    r["C2_json_parsed"] = isinstance(js, dict) and isinstance(js.get("elements"), list)
    if not r["C2_json_parsed"]:
        return {**r, **{k: False for k in ("C3_no_runtime_remark", "C4_source_timestamp",
                                           "C5_count_matches", "C6_way_structure", "C7_within_envelope")}}
    remark = (js.get("remark") or "").lower()
    r["C3_no_runtime_remark"] = not ("error" in remark or "timeout" in remark or "out of memory" in remark)
    r["C4_source_timestamp"] = parse_ts(js.get("osm3s", {}).get("timestamp_osm_base")) is not None
    els = js["elements"]
    counts = [e for e in els if e.get("type") == "count"]
    ways = [e for e in els if e.get("type") == "way"]
    expected = int(counts[0].get("tags", {}).get("ways", -1)) if counts else -1
    r["C5_count_matches"] = expected == len(ways) and expected > 0
    ok = True
    for w in ways:
        nodes, geom = w.get("nodes") or [], w.get("geometry") or []
        if (len(nodes) < 2 or len(geom) != len(nodes) or "highway" not in w.get("tags", {})
                or any(g is None or g.get("lat") is None or g.get("lon") is None for g in geom)):
            ok = False
            break
    r["C6_way_structure"] = ok and bool(ways)
    if bbox and ways:
        S, W, N, E = bbox
        r["C7_within_envelope"] = all(
            any(S <= g["lat"] <= N and W <= g["lon"] <= E for g in w["geometry"]) for w in ways)
    else:
        r["C7_within_envelope"] = bool(ways)
    return r


def fresh(request_utc: datetime, source_ts: Optional[datetime]) -> bool:
    if source_ts is None:
        return False
    age_h = (request_utc - source_ts).total_seconds() / 3600
    return -1 <= age_h <= C.MAX_SOURCE_AGE_H   # small negative tolerance for clock skew


def pair_checks(a: dict, b: dict) -> Dict[str, bool]:
    """a, b: per-city records with endpoint, request_utc, response_utc, source_ts,
    completeness (dict), core_segments_lower."""
    r = {}
    r["P1_same_endpoint"] = a["endpoint"] == b["endpoint"]
    r["P2_both_complete"] = all(a["completeness"].values()) and all(b["completeness"].values())
    r["P3_both_fresh_72h"] = fresh(a["request_utc"], a["source_ts"]) and fresh(b["request_utc"], b["source_ts"])
    if a["source_ts"] and b["source_ts"]:
        gap = abs((a["source_ts"] - b["source_ts"]).total_seconds()) / 3600
        r["P4_source_gap_24h"] = gap <= C.MAX_PAIR_SOURCE_GAP_H
    else:
        r["P4_source_gap_24h"] = False
    dur = (max(a["response_utc"], b["response_utc"]) - min(a["request_utc"], b["request_utc"])).total_seconds() / 3600
    r["P5_pair_within_24h"] = dur <= C.MAX_PAIR_DURATION_H
    r["P6_coverage_500"] = (a.get("core_segments_lower", 0) >= C.MIN_CORE_SEGMENTS
                            and b.get("core_segments_lower", 0) >= C.MIN_CORE_SEGMENTS)
    r["PAIR_VALID"] = all(r.values())
    return r
