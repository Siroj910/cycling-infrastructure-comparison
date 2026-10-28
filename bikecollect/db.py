"""Local SQLite database (issue #2). No server, no credentials: one file under data/.

Tables
  provenance       one row per collection run (data/<run_id>/provenance.json)
  sources          the Overpass services in the fixed service order
  snapshots        one row per city response saved in a run
  source_features  eligible facilities in a snapshot (one OSM way can give several, e.g. left + right lanes)
  quality_events   every check result (C1-C7 per snapshot, P1-P6 per run, load-time checks)

The database is derived data: it is not committed and can always be rebuilt from the raw
snapshots in data/ with `python -m bikecollect.load --all`.
"""
import os, sqlite3

DEFAULT_DB = os.path.join("data", "bikecollect.sqlite")
SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS provenance (
    run_id              TEXT PRIMARY KEY,
    purpose             TEXT NOT NULL,
    pair_no             INTEGER,
    approval            TEXT,
    started_utc         TEXT NOT NULL,
    finished_utc        TEXT NOT NULL,
    pair_valid          INTEGER NOT NULL CHECK (pair_valid IN (0, 1)),
    valid_endpoint      TEXT,
    git_commit          TEXT,
    uncommitted_changes INTEGER,
    config_json         TEXT NOT NULL,
    request_log_json    TEXT NOT NULL,
    provenance_sha256   TEXT NOT NULL,
    loaded_utc          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
    source_id     INTEGER PRIMARY KEY,
    endpoint      TEXT NOT NULL UNIQUE,
    service_order INTEGER
);

CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id          TEXT PRIMARY KEY,               -- <run_id>_<city>_<service_no>
    run_id               TEXT NOT NULL REFERENCES provenance(run_id),
    source_id            INTEGER NOT NULL REFERENCES sources(source_id),
    city                 TEXT NOT NULL,
    service_no           INTEGER NOT NULL,
    pair_valid           INTEGER NOT NULL CHECK (pair_valid IN (0, 1)),  -- this service's pair passed P1-P6
    complete             INTEGER NOT NULL CHECK (complete IN (0, 1)),    -- C1-C7 all passed
    http_status          INTEGER,
    request_utc          TEXT,
    response_utc         TEXT,
    source_ts            TEXT,
    query_text           TEXT NOT NULL,
    query_sha256         TEXT NOT NULL,
    raw_file             TEXT NOT NULL,
    response_sha256      TEXT NOT NULL,
    response_bytes       INTEGER,
    envelope_swne        TEXT NOT NULL,
    eligible_ways        INTEGER,
    core_segments_lower  INTEGER,
    core_segments_upper  INTEGER,
    l_km                 REAL
);
CREATE INDEX IF NOT EXISTS ix_snapshots_city ON snapshots(city, source_ts);
CREATE INDEX IF NOT EXISTS ix_snapshots_hash ON snapshots(response_sha256);

CREATE TABLE IF NOT EXISTS source_features (
    snapshot_id    TEXT NOT NULL REFERENCES snapshots(snapshot_id),
    osm_way_id     INTEGER NOT NULL,
    facility_no    INTEGER NOT NULL,                     -- position in classify() output for this way
    category       TEXT NOT NULL,
    side           TEXT,
    protection     TEXT CHECK (protection IN ('P', 'U', 'X') OR protection IS NULL),
    in_length      INTEGER NOT NULL CHECK (in_length IN (0, 1)),
    in_topology    INTEGER NOT NULL CHECK (in_topology IN (0, 1)),
    reason         TEXT,
    highway        TEXT,
    length_m       REAL NOT NULL,                        -- whole way, local metric CRS
    core_length_m  REAL NOT NULL,                        -- part inside the 8 km core square
    tags_json      TEXT NOT NULL,
    nodes_json     TEXT NOT NULL,
    geometry_json  TEXT NOT NULL,                        -- [[lon, lat], ...] WGS84
    PRIMARY KEY (snapshot_id, osm_way_id, facility_no)
);
CREATE INDEX IF NOT EXISTS ix_features_way ON source_features(osm_way_id);
CREATE INDEX IF NOT EXISTS ix_features_cat ON source_features(snapshot_id, category, protection);

CREATE TABLE IF NOT EXISTS quality_events (
    event_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT NOT NULL REFERENCES provenance(run_id),
    snapshot_id  TEXT REFERENCES snapshots(snapshot_id),    -- NULL for run-level (pair) checks
    stage        TEXT NOT NULL CHECK (stage IN ('collect', 'load')),
    check_name   TEXT NOT NULL,
    passed       INTEGER NOT NULL CHECK (passed IN (0, 1)),
    severity     TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'error')),
    detail       TEXT,
    created_utc  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_events_run ON quality_events(run_id, snapshot_id);
"""


def connect(path: str = DEFAULT_DB) -> sqlite3.Connection:
    """Open (and create if needed) the database with foreign keys enforced."""
    if path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_schema(conn)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create all tables if missing (idempotent) and record the schema version."""
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version not in (0, SCHEMA_VERSION):
        raise RuntimeError(f"database schema version {version}, code expects {SCHEMA_VERSION}")
    conn.executescript(SCHEMA)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()


def table_names(conn: sqlite3.Connection) -> list:
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
