# cycling-infrastructure-comparison
Collects bike lane data for Amsterdam and Copenhagen from OpenStreetMap, checks its quality, stores it in a database and compares how well each city’s network protects cyclists. UDE5014CM coursework.

## Collector at approval (27 Oct 2026)

```
pip install -r requirements.txt
pip install -U certifi        # fixes the TLS errors seen with overpass-api.de
python -m pytest -q           # 27 tests should pass
python -m bikecollect.feasibility_pair
```

The paired test writes to `feasibility/<run_id>/` (report.md, provenance.json, raw *.json.gz).
This is pre-approval feasibility evidence only. Never put it in `data/` or use it in assessed analysis.
To test one service only: `python -m bikecollect.feasibility_pair --endpoint https://overpass-api.de/api/interpreter`
