"""Post-approval paired collection (assessed data).

Usage:  python -m bikecollect.collect --pair N [--endpoint URL]

Runs one paired collection (Amsterdam + Copenhagen) with the approved service
order, query, timeouts, retries and C1-C7 / P1-P6 checks, and writes to
data/<run_id>/ only:
  raw_<city>_<service_no>.json.gz, provenance.json, report.md
Exit code 0 = valid pair obtained, 1 = no valid pair (still written and logged).

The collection rules are imported unchanged from the approved collector
(feasibility_pair, checks, classify, config); only the output location and the
provenance record differ.
"""
import argparse, gzip, hashlib, json, os, platform, subprocess, sys
from datetime import datetime

from . import config as C
from .checks import completeness, pair_checks, parse_ts
from .feasibility_pair import fetch, frame, metrics, now, iso

DATA_ROOT = "data"
FORBIDDEN_DIR = "feasibility"


def check_output_root(root: str) -> str:
    """Assessed data may never be written under feasibility/ (approval condition 1)."""
    parts = os.path.normpath(os.path.abspath(root)).split(os.sep)
    if FORBIDDEN_DIR in parts:
        raise ValueError(f"refusing to write assessed data under '{FORBIDDEN_DIR}/': {root}")
    return root


def code_version() -> dict:
    """Git commit of the code that collected the data, and whether it had uncommitted changes."""
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=here, capture_output=True,
                                text=True, timeout=10).stdout.strip() or "unknown"
        dirty = bool(subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=here,
                                    capture_output=True, text=True, timeout=10).stdout.strip())
    except (OSError, subprocess.SubprocessError):
        commit, dirty = "unknown", None
    return {"git_commit": commit, "uncommitted_changes": dirty}


def environment() -> dict:
    """Interpreter, OS and library versions used for the run (reproducibility)."""
    import pyproj, requests, shapely
    return {"python": platform.python_version(), "platform": platform.platform(),
            "requests": requests.__version__, "pyproj": pyproj.__version__, "shapely": shapely.__version__}


def collect(endpoints, root=DATA_ROOT, pair_no=None, fetcher=None):
    """Try services in the fixed order until one gives a valid pair. Returns (out_dir, provenance).
    fetcher defaults to the approved fetch(); tests pass a fake one (no network)."""
    check_output_root(root)
    fetcher = fetcher or fetch
    started = now()
    run_id = started.strftime("%Y%m%dT%H%M%SZ")
    out_dir = os.path.join(root, run_id)
    os.makedirs(out_dir, exist_ok=False)
    log, tried = [], []
    for service_no, ep in enumerate(endpoints, start=1):
        recs = {}
        for city in C.CITIES:
            fwd, core, bbox = frame(city)
            q = C.eligible_query(",".join(f"{v:.6f}" for v in bbox))
            status, raw, t_req, t_resp = fetcher(ep, q, log)
            js, raw_file = None, None
            if raw:
                try:
                    js = json.loads(raw)
                except ValueError:
                    js = None
                raw_file = f"raw_{city}_{service_no}.json.gz"
                with gzip.open(os.path.join(out_dir, raw_file), "wb") as fh:
                    fh.write(raw)
            comp = completeness(status or 0, js, bbox)
            rec = {"city": city, "endpoint": ep, "http_status": status,
                   "request_utc": t_req, "response_utc": t_resp,
                   "source_ts": parse_ts((js or {}).get("osm3s", {}).get("timestamp_osm_base")),
                   "query": q,
                   "query_sha256": hashlib.sha256(q.encode()).hexdigest(),
                   "raw_file": raw_file,
                   "response_sha256": hashlib.sha256(raw).hexdigest() if raw else None,
                   "response_bytes": len(raw) if raw else 0,
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
        tried.append({"service_no": service_no, "endpoint": ep, "cities": recs, "pair_checks": pc})
        if pc.get("PAIR_VALID"):
            break
    valid = next((p for p in tried if p["pair_checks"].get("PAIR_VALID")), None)
    prov = {
        "run_id": run_id,
        "purpose": "ASSESSED POST-APPROVAL COLLECTION",
        "pair_no": pair_no,
        "approval": "Approved 27 Oct 2026 (Version 3 + Addendum 26 Oct 2026)",
        "started_utc": started,
        "finished_utc": now(),
        "pair_valid": valid is not None,
        "valid_endpoint": valid["endpoint"] if valid else None,
        "code": code_version(),
        "environment": environment(),
        "config": {"service_order": list(endpoints), "server_timeout_s": C.SERVER_TIMEOUT_S,
                   "client_connect_timeout_s": C.CLIENT_CONNECT_TIMEOUT_S,
                   "client_read_timeout_s": C.CLIENT_READ_TIMEOUT_S, "retry_waits_s": C.RETRY_WAITS_S,
                   "retry_statuses": sorted(C.RETRY_STATUSES), "max_source_age_h": C.MAX_SOURCE_AGE_H,
                   "max_pair_source_gap_h": C.MAX_PAIR_SOURCE_GAP_H,
                   "max_pair_duration_h": C.MAX_PAIR_DURATION_H, "min_core_segments": C.MIN_CORE_SEGMENTS,
                   "user_agent": C.USER_AGENT},
        "pairs_tried": tried,
        "request_log": log,
    }
    write_outputs(out_dir, prov)
    return out_dir, prov


def _ser(o):
    return iso(o) if isinstance(o, datetime) else str(o)


def write_outputs(out_dir, prov):
    with open(os.path.join(out_dir, "provenance.json"), "w") as f:
        json.dump(prov, f, indent=2, default=_ser)
    L = [f"# Collection run {prov['run_id']} (pair {prov['pair_no'] or '-'})", "",
         f"Assessed post-approval collection. Pair valid: **{prov['pair_valid']}**"
         + (f" on {prov['valid_endpoint']}" if prov["valid_endpoint"] else ""),
         f"Code: {prov['code']['git_commit']} (uncommitted changes: {prov['code']['uncommitted_changes']})", ""]
    for p in prov["pairs_tried"]:
        L += [f"## Service {p['service_no']}: {p['endpoint']}", "",
              "| Item | Amsterdam | Copenhagen |", "|---|---|---|"]
        a, b = p["cities"].get("Amsterdam", {}), p["cities"].get("Copenhagen", {})
        g = lambda r, k: _ser(r.get(k)) if r.get(k) is not None else "-"
        for k in ("request_utc", "response_utc", "source_ts", "http_status", "response_sha256"):
            L.append(f"| {k} | {g(a, k)} | {g(b, k)} |")
        for k in (a.get("completeness") or {}):
            L.append(f"| {k} | {a['completeness'].get(k)} | {(b.get('completeness') or {}).get(k)} |")
        for k in ("eligible_ways", "core_segments_lower", "core_segments_upper", "L_km", "primary_P_U_X_pct",
                  "known_share_pct", "protected_ratio_P_over_PU_pct", "crossing_share_of_L_pct",
                  "P_pct_excluding_crossings", "routing_link_km_excluded_from_L"):
            L.append(f"| {k} | {g(a, k)} | {g(b, k)} |")
        L += ["", "Pair checks: " + ", ".join(f"{k}={v}" for k, v in p["pair_checks"].items()), ""]
    L += ["## Request log", "", "| service | try | request UTC | response UTC | status | bytes |",
          "|---|---|---|---|---|---|"]
    for r in prov["request_log"]:
        L.append(f"| {r['endpoint']} | {r['attempt']} | {r['request_utc']} | {r.get('response_utc', '')} | "
                 f"{r.get('status', r.get('error', ''))} | {r.get('bytes', '')} |")
    with open(os.path.join(out_dir, "report.md"), "w") as f:
        f.write("\n".join(L) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run one assessed paired collection into data/.")
    ap.add_argument("--pair", type=int, required=True, help="scheduled pair number (1-4)")
    ap.add_argument("--endpoint", help="use one service only (default: the fixed service order)")
    args = ap.parse_args(argv)
    out, prov = collect([args.endpoint] if args.endpoint else C.ENDPOINTS, pair_no=args.pair)
    print(f"Wrote {out} - pair valid: {prov['pair_valid']}")
    return 0 if prov["pair_valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
