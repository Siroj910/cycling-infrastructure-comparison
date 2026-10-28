# cycling-infrastructure-comparison
Collects bike lane data for Amsterdam and Copenhagen from OpenStreetMap, checks its quality, stores it in a database and compares how well each city’s network protects cyclists. UDE5014CM coursework.

Approved 27 Oct 2026 (Version 3 + Addendum 26 Oct 2026). Tag `approval-baseline` marks the collector as approved.

## Setup (Python 3.12)

```
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -U certifi        # fixes the TLS errors seen with overpass-api.de
python -m pytest -q           # all tests should pass before any collection
```

## Collecting an assessed pair

```
python -m bikecollect.collect --pair 1     # scheduled days: 28 Oct, 31 Oct, 4 Nov, 7 Nov (pairs 1-4)
```

Writes `data/<run_id>/`: `raw_<city>_<service>.json.gz`, `provenance.json` (full queries, query and response
SHA-256, timestamps, every attempt including failures, C1-C7 / P1-P6 results, code commit) and `report.md`.
Exit code 0 = valid pair, 1 = no valid pair. Failed runs are kept and committed: they are evidence too.
Commit the code before collecting so `provenance.json` records a clean commit.

## Feasibility run (pre-approval, not assessed)

`feasibility/20261026T142511Z/` holds the paired test from 26 Oct 2026. It is never moved into `data/` or used in
assessed analysis; `collect` refuses to write under `feasibility/`.
`python -m bikecollect.feasibility_pair` reproduces that test.
