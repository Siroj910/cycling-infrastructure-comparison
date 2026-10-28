"""Paired feasibility test from the collector (PRE-APPROVAL; never assessed data).

Usage:  python -m bikecollect.feasibility_pair  [--endpoint URL]
Writes to feasibility/<run_id>/ only (separate from data/ used for assessed snapshots):
  raw_<city>.json.gz, provenance.json, report.md
"""
import argparse, gzip, hashlib, json, os, time
from collections import Counter, defaultdict
from datetime import datetime, timezone

import requests
from pyproj import Transformer
from shapely.geometry import LineString, box
from shapely.ops import transform as shp_transform

from . import config as C
from .checks import completeness, pair_checks, parse_ts
from .classify import classify

UTC = timezone.utc
now = lambda: datetime.now(UTC)
iso = lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ") if d else None


def frame(city):
    c = C.CITIES[city]
    fwd = Transformer.from_crs(4326, c["epsg"], always_xy=True)
    inv = Transformer.from_crs(c["epsg"], 4326, always_xy=True)
    x0, y0 = fwd.transform(c["lon"], c["lat"])
    core = box(x0 - C.CORE_HALF_M, y0 - C.CORE_HALF_M, x0 + C.CORE_HALF_M, y0 + C.CORE_HALF_M)
    ctx = box(x0 - C.CONTEXT_HALF_M, y0 - C.CONTEXT_HALF_M, x0 + C.CONTEXT_HALF_M, y0 + C.CONTEXT_HALF_M)
    lons, lats = zip(*[inv.transform(x, y) for x, y in ctx.exterior.coords])
    return fwd, core, (min(lats), min(lons), max(lats), max(lons))


def fetch(endpoint, query, log):
    """One request with at most two retries. Returns (status, bytes, req_utc, resp_utc)."""
    for attempt, wait in enumerate([0] + C.RETRY_WAITS_S):
        if wait:
            time.sleep(wait)
        t_req = now()
        rec = {"endpoint": endpoint, "attempt": attempt + 1, "request_utc": iso(t_req)}
        try:
            r = requests.post(endpoint, data={"data": query}, headers={"User-Agent": C.USER_AGENT},
                              timeout=(C.CLIENT_CONNECT_TIMEOUT_S, C.CLIENT_READ_TIMEOUT_S))
            t_resp = now()
            rec.update(status=r.status_code, bytes=len(r.content), response_utc=iso(t_resp),
                       sha256=hashlib.sha256(r.content).hexdigest())
            log.append(rec)
            if r.status_code in C.RETRY_STATUSES:
                continue
            return r.status_code, r.content, t_req, t_resp
        except requests.RequestException as e:
            rec.update(error=type(e).__name__ + ": " + str(e)[:160], response_utc=iso(now()))
            log.append(rec)
    return None, None, None, None


def metrics(js, fwd, core):
    ways = [e for e in js["elements"] if e.get("type") == "way"]
    elig = [(w, classify(w.get("tags", {}))) for w in ways]
    elig = [(w, f) for w, f in elig if f]
    use, ends = Counter(), Counter()
    topo = [(w, f) for w, f in elig if any(x.in_topology for x in f)]
    for w, _ in topo:
        for n in w["nodes"]:
            use[n] += 1
        ends[w["nodes"][0]] += 1
        ends[w["nodes"][-1]] += 1
    deg = Counter()
    L, cat_len, excl_len = Counter(), Counter(), Counter()
    pieces_core = 0
    proj = lambda x, y, z=None: fwd.transform(x, y)
    for w, facs in topo:
        coords = [(g["lon"], g["lat"]) for g in w["geometry"]]
        nodes = w["nodes"]
        idx = [0] + [i for i in range(1, len(nodes) - 1) if use[nodes[i]] > 1] + [len(nodes) - 1]
        for a, b in zip(idx, idx[1:]):
            seg = shp_transform(proj, LineString(coords[a:b + 1]))
            if seg.length == 0:
                continue
            deg[nodes[a]] += 1
            deg[nodes[b]] += 1
            km = seg.intersection(core).length / 1000
            if km == 0:
                continue
            if any(f.in_length for f in facs):
                pieces_core += 1
            for f in facs:
                if f.in_length:
                    L[f.protection] += km
                    cat_len[f.category] += km
                else:
                    excl_len[f.category] += km
    deg2_joins = sum(1 for n, d in deg.items() if d == 2 and ends[n] >= 2 and use[n] == ends[n])
    tot = sum(L.values())
    pct = lambda k: round(100 * L[k] / tot, 1) if tot else None
    no_cross = tot - cat_len.get("crossing", 0)
    return {
        "eligible_ways": len(elig),
        "core_segments_upper": pieces_core,
        "core_segments_lower": max(pieces_core - deg2_joins, 0),
        "L_km": round(tot, 2),
        "primary_P_U_X_km": {k: round(L[k], 2) for k in ("P", "U", "X")},
        "primary_P_U_X_pct": {k: pct(k) for k in ("P", "U", "X")},
        "known_share_pct": round(100 * (L["P"] + L["U"]) / tot, 1) if tot else None,
        "protected_ratio_P_over_PU_pct": round(100 * L["P"] / (L["P"] + L["U"]), 1) if L["P"] + L["U"] else None,
        "length_by_category_km": {k: round(v, 2) for k, v in sorted(cat_len.items())},
        "crossing_share_of_L_pct": round(100 * cat_len.get("crossing", 0) / tot, 1) if tot else None,
        "P_pct_excluding_crossings": round(100 * L["P"] / no_cross, 1) if no_cross else None,
        "routing_link_km_excluded_from_L": round(excl_len.get("routing_link", 0), 2),
    }


def run(endpoints):
    run_id = now().strftime("%Y%m%dT%H%M%SZ")
    out_dir = os.path.join("feasibility", run_id)
    os.makedirs(out_dir, exist_ok=True)
    log, tried = [], []
    for ep in endpoints:
        recs = {}
        for city in C.CITIES:
            fwd, core, bbox = frame(city)
            q = C.eligible_query(",".join(f"{v:.6f}" for v in bbox))
            status, raw, t_req, t_resp = fetch(ep, q, log)
            js = None
            if raw:
                try:
                    js = json.loads(raw)
                except ValueError:
                    js = None
                with gzip.open(os.path.join(out_dir, f"raw_{city}_{len(tried)}.json.gz"), "wb") as fh:
                    fh.write(raw)
            comp = completeness(status or 0, js, bbox)
            rec = {"city": city, "endpoint": ep, "request_utc": t_req, "response_utc": t_resp,
                   "source_ts": parse_ts((js or {}).get("osm3s", {}).get("timestamp_osm_base")),
                   "query_sha256": hashlib.sha256(q.encode()).hexdigest(),
                   "response_sha256": hashlib.sha256(raw).hexdigest() if raw else None,
                   "envelope_SWNE": [round(v, 6) for v in bbox], "completeness": comp}
            if all(comp.values()):
                rec.update(metrics(js, fwd, core))
            recs[city] = rec
            if t_req is None:
                break
        if len(recs) == 2 and recs["Amsterdam"]["request_utc"] and recs["Copenhagen"]["request_utc"]:
            pc = pair_checks(recs["Amsterdam"], recs["Copenhagen"])
        else:
            pc = {"PAIR_VALID": False, "note": "a request failed"}
        tried.append({"endpoint": ep, "cities": recs, "pair_checks": pc})
        if pc.get("PAIR_VALID"):
            break
    write(out_dir, run_id, tried, log)
    return out_dir


def _ser(o):
    return iso(o) if isinstance(o, datetime) else str(o)


def write(out_dir, run_id, tried, log):
    with open(os.path.join(out_dir, "provenance.json"), "w") as f:
        json.dump({"run_id": run_id, "purpose": "PRE-APPROVAL FEASIBILITY ONLY - not assessed data",
                   "pairs_tried": tried, "request_log": log}, f, indent=2, default=_ser)
    L = [f"# Paired feasibility test {run_id}", "", "Pre-approval feasibility only; not assessed data.", ""]
    for p in tried:
        L += [f"## Service: {p['endpoint']}", "",
              "| Item | Amsterdam | Copenhagen |", "|---|---|---|"]
        a, b = p["cities"].get("Amsterdam", {}), p["cities"].get("Copenhagen", {})
        g = lambda r, k: _ser(r.get(k)) if r.get(k) is not None else "-"
        for k in ("request_utc", "response_utc", "source_ts"):
            L.append(f"| {k} | {g(a, k)} | {g(b, k)} |")
        for k in (a.get("completeness") or {}):
            L.append(f"| {k} | {a['completeness'].get(k)} | {(b.get('completeness') or {}).get(k)} |")
        for k in ("eligible_ways", "core_segments_lower", "core_segments_upper", "L_km", "primary_P_U_X_pct",
                  "known_share_pct", "protected_ratio_P_over_PU_pct", "crossing_share_of_L_pct",
                  "P_pct_excluding_crossings", "routing_link_km_excluded_from_L", "length_by_category_km"):
            L.append(f"| {k} | {g(a, k)} | {g(b, k)} |")
        L += ["", "Pair checks: " + ", ".join(f"{k}={v}" for k, v in p["pair_checks"].items()), ""]
    L += ["## Request log", "", "| service | try | request UTC | response UTC | status | bytes |", "|---|---|---|---|---|---|"]
    for r in log:
        L.append(f"| {r['endpoint']} | {r['attempt']} | {r['request_utc']} | {r.get('response_utc', '')} | "
                 f"{r.get('status', r.get('error', ''))} | {r.get('bytes', '')} |")
    with open(os.path.join(out_dir, "report.md"), "w") as f:
        f.write("\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", help="test one service only")
    args = ap.parse_args()
    out = run([args.endpoint] if args.endpoint else C.ENDPOINTS)
    print("Wrote", out, "- send report.md and provenance.json")


if __name__ == "__main__":
    main()
