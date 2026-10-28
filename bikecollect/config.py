"""Frozen configuration for collection (proposal v3 + addendum)."""

# Study windows: reference point (WGS84) and local metric CRS
CITIES = {
    "Amsterdam": {"lat": 52.3731, "lon": 4.8922, "epsg": 32631},
    "Copenhagen": {"lat": 55.6761, "lon": 12.5683, "epsg": 32633},
}
CORE_HALF_M = 4000      # 8 km core square
CONTEXT_HALF_M = 5000   # core + 1 km buffer
CELL_M = 1000           # 64 cells of 1 km

# Fixed service order: external Overpass API services only (no downloaded extracts)
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

# Timeouts (one consistent rule): Overpass server limit in the query,
# client read limit = server limit + 60 s margin.
SERVER_TIMEOUT_S = 180
CLIENT_CONNECT_TIMEOUT_S = 30
CLIENT_READ_TIMEOUT_S = SERVER_TIMEOUT_S + 60   # 240
RETRY_WAITS_S = [30, 120]   # at most two retries per service (main instance asks for >=30 s after 429/406)
RETRY_STATUSES = {406, 429, 502, 503, 504}

# Freshness and pairing rule
MAX_SOURCE_AGE_H = 72        # request time minus source timestamp
MAX_PAIR_SOURCE_GAP_H = 24   # |source timestamp A - source timestamp B|
MAX_PAIR_DURATION_H = 24     # first request start to last response end
MIN_CORE_SEGMENTS = 500

USER_AGENT = "UDEA-UDE5014CM-bicycle-collector/0.2 (student 50000310; coursework)"


def eligible_query(bbox: str) -> str:
    """Eligible cycling ways for one envelope. Count and data come from ONE
    response (same database state), so the count is a completeness check."""
    b = bbox
    return f"""[out:json][timeout:{SERVER_TIMEOUT_S}];
(
  way["highway"="cycleway"]({b});
  way["highway"~"^(path|footway)$"]["bicycle"="designated"]({b});
  way["highway"]["cycleway"~"^(lane|track)$"]({b});
  way["highway"]["cycleway:both"~"^(lane|track)$"]({b});
  way["highway"]["cycleway:left"~"^(lane|track)$"]({b});
  way["highway"]["cycleway:right"~"^(lane|track)$"]({b});
  way["highway"]["cyclestreet"="yes"]({b});
  way["highway"]["bicycle_road"="yes"]({b});
)->.e;
.e out count;
.e out body geom;"""
