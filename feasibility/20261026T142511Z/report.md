# Paired feasibility test 20261026T142511Z

Pre-approval feasibility only; not assessed data.

## Service: https://overpass-api.de/api/interpreter

| Item | Amsterdam | Copenhagen |
|---|---|---|
| request_utc | - | - |
| response_utc | - | - |
| source_ts | - | - |
| C1_http_200 | False | None |
| C2_json_parsed | False | None |
| C3_no_runtime_remark | False | None |
| C4_source_timestamp | False | None |
| C5_count_matches | False | None |
| C6_way_structure | False | None |
| C7_within_envelope | False | None |
| eligible_ways | - | - |
| core_segments_lower | - | - |
| core_segments_upper | - | - |
| L_km | - | - |
| primary_P_U_X_pct | - | - |
| known_share_pct | - | - |
| protected_ratio_P_over_PU_pct | - | - |
| crossing_share_of_L_pct | - | - |
| P_pct_excluding_crossings | - | - |
| routing_link_km_excluded_from_L | - | - |
| length_by_category_km | - | - |

Pair checks: PAIR_VALID=False, note=a request failed

## Service: https://maps.mail.ru/osm/tools/overpass/api/interpreter

| Item | Amsterdam | Copenhagen |
|---|---|---|
| request_utc | 2026-10-26T14:27:42Z | 2026-10-26T14:28:30Z |
| response_utc | 2026-10-26T14:27:58Z | 2026-10-26T14:28:57Z |
| source_ts | 2026-10-26T14:26:34Z | 2026-10-26T14:27:36Z |
| C1_http_200 | True | True |
| C2_json_parsed | True | True |
| C3_no_runtime_remark | True | True |
| C4_source_timestamp | True | True |
| C5_count_matches | True | True |
| C6_way_structure | True | True |
| C7_within_envelope | True | True |
| eligible_ways | 7711 | 4841 |
| core_segments_lower | 3326 | 2024 |
| core_segments_upper | 7358 | 4424 |
| L_km | 421.12 | 381.0 |
| primary_P_U_X_pct | {'P': 87.2, 'U': 12.8, 'X': 0.0} | {'P': 91.4, 'U': 8.6, 'X': 0.0} |
| known_share_pct | 100.0 | 100.0 |
| protected_ratio_P_over_PU_pct | 87.2 | 91.4 |
| crossing_share_of_L_pct | 0.4 | 0.4 |
| P_pct_excluding_crossings | 87.6 | 91.8 |
| routing_link_km_excluded_from_L | 0.01 | 0.05 |
| length_by_category_km | {'crossing': 1.87, 'cycle_street': 7.71, 'road_lane': 44.19, 'road_track': 2.3, 'separate_path': 362.11, 'shared_path': 2.94} | {'crossing': 1.52, 'cycle_street': 5.8, 'road_lane': 25.39, 'road_track': 195.79, 'separate_path': 108.44, 'shared_path': 44.06} |

Pair checks: P1_same_endpoint=True, P2_both_complete=True, P3_both_fresh_72h=True, P4_source_gap_24h=True, P5_pair_within_24h=True, P6_coverage_500=True, PAIR_VALID=True

## Request log

| service | try | request UTC | response UTC | status | bytes |
|---|---|---|---|---|---|
| https://overpass-api.de/api/interpreter | 1 | 2026-10-26T14:25:11Z | 2026-10-26T14:25:12Z | SSLError: HTTPSConnectionPool(host='overpass-api.de', port=443): Max retries exceeded with url: /api/interpreter (Caused by SSLError(SSLError(1, '[SSL: SSLV3_ALERT_HANDSH |  |
| https://overpass-api.de/api/interpreter | 2 | 2026-10-26T14:25:42Z | 2026-10-26T14:25:42Z | SSLError: HTTPSConnectionPool(host='overpass-api.de', port=443): Max retries exceeded with url: /api/interpreter (Caused by SSLError(SSLError(1, '[SSL: SSLV3_ALERT_HANDSH |  |
| https://overpass-api.de/api/interpreter | 3 | 2026-10-26T14:27:42Z | 2026-10-26T14:27:42Z | SSLError: HTTPSConnectionPool(host='overpass-api.de', port=443): Max retries exceeded with url: /api/interpreter (Caused by SSLError(SSLError(1, '[SSL: SSLV3_ALERT_HANDSH |  |
| https://maps.mail.ru/osm/tools/overpass/api/interpreter | 1 | 2026-10-26T14:27:42Z | 2026-10-26T14:27:58Z | 200 | 6661325 |
| https://maps.mail.ru/osm/tools/overpass/api/interpreter | 1 | 2026-10-26T14:27:59Z | 2026-10-26T14:28:00Z | 504 | 160 |
| https://maps.mail.ru/osm/tools/overpass/api/interpreter | 2 | 2026-10-26T14:28:30Z | 2026-10-26T14:28:57Z | 200 | 4327527 |
