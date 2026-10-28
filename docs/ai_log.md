# AI use log

Dated record of AI assistance (tool, what was asked, what was produced, what I checked or changed).
Commits made with AI help carry a `Co-Authored-By: Claude` trailer.

## 2026-10-28 (Wed)

- **Tool:** Claude (Anthropic), chat session.
- **Asked:** set up the repository from my approved collector, write the six Week 6 issues, and build the `collect` command (issue #1).
- **Produced:**
  - Baseline commit of the approved collector (no code changes; 27 tests pass on Python 3.12).
  - Issues #1-#6 with acceptance criteria.
  - `bikecollect/collect.py` (writes assessed pairs to `data/`, refuses `feasibility/`, records full queries, hashes, timestamps, attempts and code commit) and `tests/test_collect.py` (3 tests, no network). Collection rules are imported unchanged from the approved collector.
- **Checked:** all 30 tests pass; replaying the 26 Oct feasibility responses through `collect` gives the same counts and pair checks as the 26 Oct report (Amsterdam 3,326 / Copenhagen 2,024 lower-bound core segments, PAIR_VALID).
- **Also produced (issues #2, #3):** `bikecollect/db.py` (five-table SQLite schema, foreign keys and CHECK constraints enforced) with 2 tests; `bikecollect/load.py` (loads `data/<run_id>/` runs, verifies raw-file hashes, idempotent, refuses feasibility runs) with 4 tests. 36 tests in total.
- **Checked (loader):** loading the replayed 26 Oct pair gives 7,711 / 4,841 eligible ways and 421.1 / 381.0 km core length, matching the collector; 43 / 27 query-matched ways excluded by the classification rules are logged as warnings.
- **My review / changes:** _to fill in_
