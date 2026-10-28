from bikecollect.classify import classify


def one(tags, strict=False):
    r = classify(tags, strict)
    assert len(r) == 1, r
    return r[0]


# --- crossings: never protected just because highway=cycleway -----------------
def test_cycleway_crossing_is_unprotected_not_protected():
    f = one({"highway": "cycleway", "cycleway": "crossing"})
    assert f.category == "crossing" and f.protection == "U" and f.in_length and f.in_topology


def test_footway_crossing_designated_is_crossing():
    f = one({"highway": "footway", "footway": "crossing", "bicycle": "designated"})
    assert f.category == "crossing" and f.protection == "U"


def test_crossing_key_on_cycleway_is_crossing():
    f = one({"highway": "cycleway", "crossing": "traffic_signals"})
    assert f.category == "crossing" and f.protection == "U"


def test_grade_separated_crossing_goes_to_review():
    f = one({"highway": "cycleway", "cycleway": "crossing", "bridge": "yes"})
    assert f.protection == "X"


def test_footway_crossing_without_designation_not_eligible():
    assert classify({"highway": "footway", "footway": "crossing", "bicycle": "yes"}) == []


# --- routing links: topology only -------------------------------------------
def test_cycleway_link_is_topology_only():
    f = one({"highway": "cycleway", "cycleway": "link"})
    assert f.category == "routing_link" and not f.in_length and f.in_topology and f.protection is None


# --- primary rule vs strict reading -------------------------------------------
def test_separate_path_primary_protected_strict_unknown():
    assert one({"highway": "cycleway"}).protection == "P"
    assert one({"highway": "cycleway"}, strict=True).protection == "X"


def test_separately_mapped_lane_is_unprotected():
    assert one({"highway": "cycleway", "cycleway": "lane"}).protection == "U"


def test_separate_path_separation_no_is_unprotected():
    assert one({"highway": "cycleway", "separation": "no"}).protection == "U"


def test_shared_path_category():
    f = one({"highway": "path", "bicycle": "designated", "foot": "designated", "segregated": "no"})
    assert f.category == "shared_path"


# --- road-side facilities -----------------------------------------------------
def test_road_both_sides_creates_two_records():
    r = classify({"highway": "secondary", "cycleway:both": "track"})
    assert [x.side for x in r] == ["left", "right"] and all(x.protection == "P" for x in r)


def test_lane_with_traffic_side_kerb_is_protected():
    f = one({"highway": "secondary", "cycleway:right": "lane", "cycleway:right:separation:left": "kerb"})
    assert f.protection == "P"


def test_track_with_separation_no_is_unprotected():
    f = one({"highway": "secondary", "cycleway:right": "track", "cycleway:right:separation": "no"})
    assert f.protection == "U"


def test_contradictory_separation_is_unknown():
    f = one({"highway": "secondary", "cycleway:right": "track", "cycleway:right:separation": "no;kerb"})
    assert f.protection == "X"


def test_unsided_lane_flags_side_unknown():
    f = one({"highway": "tertiary", "cycleway": "lane"})
    assert f.side == "unknown" and f.protection == "U"


def test_cycle_street_is_unprotected():
    assert one({"highway": "residential", "cyclestreet": "yes"}).protection == "U"


# --- exclusions ---------------------------------------------------------------
def test_exclusions():
    assert classify({"highway": "cycleway", "access": "private"}) == []
    assert classify({"highway": "cycleway", "bicycle": "no"}) == []
    assert classify({"highway": "cycleway", "bicycle:conditional": "no @ (22:00-06:00)"}) == []
    assert classify({"highway": "construction", "construction": "cycleway"}) == []
    assert classify({"highway": "residential"}) == []
