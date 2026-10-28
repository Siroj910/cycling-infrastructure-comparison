"""Load collected runs from data/<run_id>/ into the local database (issue #3).

Usage:  python -m bikecollect.load data/<run_id> [...]     load one or more runs
        python -m bikecollect.load --all                    load every run under data/
        add --db PATH to use another database file (default data/bikecollect.sqlite)

Every city response saved in a run becomes a snapshot. Before a snapshot is loaded, the raw
file is hashed and compared with provenance.json; a mismatch is recorded as a quality event and
that snapshot is not loaded. Loading a run that is already in the database does nothing.
"""
import argparse, gzip, hashlib, json, os, sys
from datetime import datetime, timezone

from shapely.geometry import LineString
from shapely.ops import transform as shp_transform

from . import db as D
from .classify import classify
from .collect import DATA_ROOT, FORBIDDEN_DIR
from .feasibility_pair import frame

ASSESSED = "ASSESSED POST-APPROVAL COLLECTION"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_file(path, gz=False):
    opener = gzip.open if gz else open
    with opener(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _event(conn, run_id, snapshot_id, stage, check, passed, severity, detail=None):
    conn.execute("""INSERT INTO quality_events (run_id, snapshot_id, stage, check_name, passed, severity,
                    detail, created_utc) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                 (run_id, snapshot_id, stage, check, int(bool(passed)), severity, detail, _now()))


def _source_id(conn, endpoint, order):
    conn.execute("INSERT OR IGNORE INTO sources (endpoint, service_order) VALUES (?, ?)", (endpoint, order))
    return conn.execute("SELECT source_id FROM sources WHERE endpoint = ?", (endpoint,)).fetchone()[0]


def _features(js, city):
    """Eligible facilities from one raw response: rows for source_features (+ count of unclassified ways)."""
    fwd, core, _ = frame(city)
    proj = lambda x, y, z=None: fwd.transform(x, y)
    rows, unclassified = [], 0
    for w in js.get("elements", []):
        if w.get("type") != "way":
            continue
        tags = w.get("tags", {})
        facs = classify(tags)
        if not facs:
            unclassified += 1
            continue
        coords = [(g["lon"], g["lat"]) for g in w["geometry"]]
        line = shp_transform(proj, LineString(coords))
        length, core_len = line.length, line.intersection(core).length
        for i, f in enumerate(facs):
            rows.append((w["id"], i, f.category, f.side, f.protection, int(f.in_length), int(f.in_topology),
                         f.reason, tags.get("highway"), round(length, 2), round(core_len, 2),
                         json.dumps(tags, sort_keys=True), json.dumps(w["nodes"]), json.dumps(coords)))
    return rows, unclassified


def check_run_dir(run_dir):
    parts = os.path.normpath(os.path.abspath(run_dir)).split(os.sep)
    if FORBIDDEN_DIR in parts:
        raise ValueError(f"refusing to load a feasibility run (not assessed data): {run_dir}")


def load_run(conn, run_dir):
    """Load one run. Returns a summary dict with status 'loaded' or 'already_loaded'."""
    check_run_dir(run_dir)
    prov_path = os.path.join(run_dir, "provenance.json")
    with open(prov_path) as fh:
        prov = json.load(fh)
    if prov.get("purpose") != ASSESSED:
        raise ValueError(f"{run_dir}: purpose is {prov.get('purpose')!r}, not assessed collection")
    run_id = prov["run_id"]
    if conn.execute("SELECT 1 FROM provenance WHERE run_id = ?", (run_id,)).fetchone():
        return {"run_id": run_id, "status": "already_loaded"}

    summary = {"run_id": run_id, "status": "loaded", "snapshots": 0, "features": 0, "refused": []}
    code = prov.get("code") or {}
    with conn:  # one transaction per run: all or nothing
        conn.execute("""INSERT INTO provenance VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                     (run_id, prov["purpose"], prov.get("pair_no"), prov.get("approval"), prov["started_utc"],
                      prov["finished_utc"], int(bool(prov["pair_valid"])), prov.get("valid_endpoint"),
                      code.get("git_commit"),
                      None if code.get("uncommitted_changes") is None else int(code["uncommitted_changes"]),
                      json.dumps(prov.get("config", {})), json.dumps(prov.get("request_log", [])),
                      _sha256_file(prov_path), _now()))
        order = {ep: i for i, ep in enumerate((prov.get("config") or {}).get("service_order", []), start=1)}
        for p in prov["pairs_tried"]:
            pair_ok = bool(p["pair_checks"].get("PAIR_VALID"))
            for k, v in p["pair_checks"].items():
                if isinstance(v, bool):
                    _event(conn, run_id, None, "collect", k, v, "info" if v else "warning",
                           f"service {p['service_no']}: {p['endpoint']}")
            for city, rec in p["cities"].items():
                if not rec.get("raw_file"):
                    _event(conn, run_id, None, "collect", "response_received", False, "warning",
                           f"{city}, service {p['service_no']}: no response saved")
                    continue
                sid = f"{run_id}_{city}_{p['service_no']}"
                raw_path = os.path.join(run_dir, rec["raw_file"])
                actual = _sha256_file(raw_path, gz=True) if os.path.exists(raw_path) else None
                if actual != rec["response_sha256"]:
                    _event(conn, run_id, None, "load", "raw_hash_matches", False, "error",
                           f"{sid}: expected {rec['response_sha256']}, found {actual}; snapshot not loaded")
                    summary["refused"].append(sid)
                    continue
                with gzip.open(raw_path, "rb") as fh:
                    js = json.loads(fh.read())
                comp = rec.get("completeness") or {}
                conn.execute("""INSERT INTO snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                             (sid, run_id, _source_id(conn, rec["endpoint"], order.get(rec["endpoint"])), city,
                              p["service_no"], int(pair_ok), int(bool(comp) and all(comp.values())),
                              rec.get("http_status"), rec.get("request_utc"), rec.get("response_utc"),
                              rec.get("source_ts"), rec["query"], rec["query_sha256"], rec["raw_file"],
                              rec["response_sha256"], rec.get("response_bytes"), json.dumps(rec["envelope_SWNE"]),
                              rec.get("eligible_ways"), rec.get("core_segments_lower"),
                              rec.get("core_segments_upper"), rec.get("L_km")))
                _event(conn, run_id, sid, "load", "raw_hash_matches", True, "info")
                for k, v in comp.items():
                    _event(conn, run_id, sid, "collect", k, v, "info" if v else "error")
                rows, unclassified = _features(js, city)
                conn.executemany("INSERT INTO source_features VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                 [(sid,) + r for r in rows])
                _event(conn, run_id, sid, "load", "features_loaded", True, "info", f"{len(rows)} facilities")
                if unclassified:
                    _event(conn, run_id, sid, "load", "all_ways_classified", False, "warning",
                           f"{unclassified} ways returned by the query had no eligible facility")
                summary["snapshots"] += 1
                summary["features"] += len(rows)
    return summary


def run_dirs(root=DATA_ROOT):
    if not os.path.isdir(root):
        return []
    return sorted(os.path.join(root, d) for d in os.listdir(root)
                  if os.path.isfile(os.path.join(root, d, "provenance.json")))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Load collected runs into the local SQLite database.")
    ap.add_argument("runs", nargs="*", help="data/<run_id> folders")
    ap.add_argument("--all", action="store_true", help="load every run under data/")
    ap.add_argument("--db", default=D.DEFAULT_DB)
    args = ap.parse_args(argv)
    dirs = run_dirs() if args.all else args.runs
    if not dirs:
        ap.error("give one or more data/<run_id> folders, or --all")
    conn = D.connect(args.db)
    failed = 0
    for d in dirs:
        s = load_run(conn, d)
        print(s)
        failed += bool(s.get("refused"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
