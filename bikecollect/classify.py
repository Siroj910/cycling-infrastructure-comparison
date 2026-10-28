"""Facility classification rules (primary rule + strict sensitivity reading).

Pure functions on an OSM tag dict, so every rule is unit-testable.

Precedence: exclusion -> routing link -> crossing -> separate path -> road-side -> cycle street.
"""
from dataclasses import dataclass
from typing import List, Optional

PHYSICAL = {"bollard", "flex_post", "vertical_panel", "bump", "planter",
            "kerb", "greenery", "hedge", "tree_row"}


@dataclass(frozen=True)
class Facility:
    category: str            # separate_path | shared_path | road_lane | road_track | crossing | cycle_street | routing_link
    side: Optional[str]      # None | left | right | unknown
    protection: Optional[str]  # P | U | X ; None = not part of facility length (routing link)
    in_length: bool          # counts in L (density, protection ratio)
    in_topology: bool        # used to connect the network graph
    reason: str


def excluded(t: dict) -> Optional[str]:
    if t.get("highway") in ("proposed", "construction", "steps") or t.get("route") == "ferry":
        return "status/steps/ferry"
    if t.get("bicycle") == "no":
        return "bicycle=no"
    if t.get("access") in ("no", "private") and t.get("bicycle") not in ("yes", "designated"):
        return "access"
    if any(k.endswith(":conditional") and k.split(":")[0] in ("access", "bicycle") for k in t):
        return "conditional"
    return None


def _vals(v: Optional[str]) -> set:
    return set(v.split(";")) if v else set()


def _is_link(t: dict) -> bool:
    return t.get("cycleway") == "link"


def _is_crossing(t: dict) -> bool:
    return (t.get("cycleway") == "crossing" or t.get("footway") == "crossing"
            or t.get("path") == "crossing" or "crossing" in t and t.get("highway") in ("cycleway", "path", "footway"))


def _separate_path(t: dict) -> bool:
    hw = t.get("highway")
    return hw == "cycleway" or (hw in ("path", "footway") and t.get("bicycle") == "designated")


def _side_sep(t: dict, side: str) -> set:
    traffic = "left" if side == "right" else "right"
    vals = set()
    for k in (f"cycleway:{side}:separation:{traffic}", f"cycleway:{side}:separation",
              f"cycleway:both:separation:{traffic}", "cycleway:both:separation", "cycleway:separation"):
        vals |= _vals(t.get(k))
    return vals


def _label(kind: str, sep: set, strict: bool) -> (str, str):
    """kind in {'path','track','lane'}; returns (protection, reason)."""
    phys, no = bool(sep & PHYSICAL), "no" in sep
    if phys and no:
        return "X", "contradictory separation values"
    unrecognised = sep - PHYSICAL - {"no"}
    if unrecognised and not phys and not no:
        return "X", "unrecognised separation value"
    if kind == "lane":
        return ("P", "lane with traffic-side physical separation") if phys else ("U", "painted lane")
    if no:
        return "U", f"{kind} with separation=no"
    if kind == "track" or phys:
        return "P", f"{kind}: track or physical separation"
    # separately mapped path without separation evidence
    if strict:
        return "X", "separate path without separation tag (strict reading)"
    return "P", "separately mapped path, off carriageway (primary rule)"


def classify(t: dict, strict: bool = False) -> List[Facility]:
    """Return facility records for one way; [] if not eligible."""
    if excluded(t):
        return []
    hw = t.get("highway")

    # 1. routing-only link: topology only, never facility length or protection
    if _is_link(t):
        return [Facility("routing_link", None, None, False, True, "cycleway=link routing aid")]

    # 2. crossing of a carriageway: always its own category
    if _is_crossing(t) and _separate_path(t):
        if t.get("bridge") not in (None, "no") or t.get("tunnel") not in (None, "no"):
            return [Facility("crossing", None, "X", True, True, "crossing tagged as grade-separated: review")]
        return [Facility("crossing", None, "U", True, True, "at-grade crossing of motor traffic")]

    # 3. separately mapped path
    if _separate_path(t):
        shared = hw != "cycleway" or (t.get("foot") == "designated" and t.get("segregated") == "no")
        cat = "shared_path" if shared else "separate_path"
        own = t.get("cycleway")
        sep = _vals(t.get("separation"))
        if own == "lane":
            p, why = _label("lane", sep, strict)
        elif own == "track":
            p, why = _label("track", sep, strict)
        else:
            p, why = _label("path", sep, strict)
        return [Facility(cat, None, p, True, True, why)]

    # 4. road-side facilities, one record per stated side
    recs = []
    for side in ("left", "right"):
        v = t.get(f"cycleway:{side}") or t.get("cycleway:both")
        if v in ("lane", "track"):
            p, why = _label(v, _side_sep(t, side), strict)
            recs.append(Facility("road_" + v, side, p, True, True, why))
    if not recs and t.get("cycleway") in ("lane", "track"):
        v = t["cycleway"]
        p, why = _label(v, _vals(t.get("separation")) | _vals(t.get("cycleway:separation")), strict)
        recs.append(Facility("road_" + v, "unknown", p, True, True, why))
    if recs:
        return recs

    # 5. cycle street: shared carriageway
    if t.get("cyclestreet") == "yes" or t.get("bicycle_road") == "yes":
        return [Facility("cycle_street", None, "U", True, True, "cycle street, shared carriageway")]
    return []
