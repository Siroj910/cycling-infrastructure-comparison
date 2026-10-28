#!/bin/bash
# One scheduled collection day: pull, test, collect, load, commit, push.
# Usage (from the repo folder on the Mac):  scripts/run_pair.sh <pair number 1-4>
# Schedule: pair 1 = 28 Oct, 2 = 31 Oct, 3 = 4 Nov, 4 = 7 Nov 2026.
PAIR="$1"
case "$PAIR" in 1|2|3|4) ;; *) echo "usage: scripts/run_pair.sh <1-4>"; exit 2;; esac
cd "$(dirname "$0")/.." || exit 1
LOG="pair${PAIR}_run.log"
exec > >(tee -a "$LOG") 2>&1
stop() { echo "STOP: $1"; echo "=== DONE (stopped) ==="; exit 1; }
echo "=== Pair $PAIR run started $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
export GIT_TERMINAL_PROMPT=0

echo "--- git pull"
git pull --ff-only || stop "git pull failed"
[ -z "$(git status --porcelain --untracked-files=no)" ] || stop "uncommitted code changes; commit them first so provenance records a clean commit"

PY=""
for p in python3.12 /opt/homebrew/bin/python3.12 /usr/local/bin/python3.12 \
         /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 "$HOME/.local/bin/python3.12"; do
  if command -v "$p" >/dev/null 2>&1; then PY="$p"; break; fi
done
[ -n "$PY" ] || stop "python3.12 not found"
echo "--- using $PY ($($PY --version))"
[ -d .venv ] || "$PY" -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt && pip install -q -U certifi || stop "pip install failed"

echo "--- tests"
python -m pytest -q -p no:warnings || stop "tests failed, not collecting"

echo "--- collect pair $PAIR $(date -u +%H:%M:%SZ)"
python -m bikecollect.collect --pair "$PAIR"
RC=$?
RUN=$(ls -1d data/2*/ | tail -1)
echo "--- collect exit code $RC, run folder $RUN"

echo "--- load into database"
python -m bikecollect.load --all

echo "--- commit and push"
if [ "$RC" = "0" ]; then STATUS="valid pair"; else STATUS="NO valid pair (kept as evidence)"; fi
git add data/ && git commit -m "Pair $PAIR ($(date +%-d\ %b\ %Y)): $STATUS" -m "Run ${RUN%/}. Collected with scripts/run_pair.sh $PAIR."
git push origin main && echo "PUSH_OK" || echo "PUSH_FAILED"
echo "=== DONE $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
