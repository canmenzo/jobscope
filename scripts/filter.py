"""Coarse gate before scoring. Keep a role only if ALL are true:
  - title is not an obvious non-tech function (sales/marketing/HR/...)
  - location is in the USA (or US-remote / unspecified)
  - does not require an active security clearance
  - matches at least one keyword from the user's selected sub-sectors/titles

Returns (kept, dropped) where dropped is a list of (job, reason).
Driven entirely by `scope` (built from config + taxonomy) — no hardcoded sector.
"""
import re

CLEARANCE_TERMS = [
    "clearance", "ts/sci", "ts sci", "top secret", "public trust",
    "dod clearance", "active clearance", "secret clearance", "polygraph",
]

NON_US_MARKERS = [
    # regions / countries
    "emea", "apac", "uk", "u.k.", "united kingdom", "england", "scotland",
    "wales", "ireland", "india", "germany", "canada", "australia", "singapore",
    "europe", "european", "latam", "poland", "spain", "france", "netherlands",
    "belgium", "luxembourg", "brazil", "mexico", "japan", "philippines",
    "romania", "bulgaria", "portugal", "israel", "switzerland", "sweden",
    "norway", "denmark", "finland", "austria", "czech", "czechia", "hungary",
    "greece", "slovenia", "croatia", "serbia", "ukraine", "turkey", "uae",
    "saudi", "egypt", "kenya", "nigeria", "south africa", "new zealand",
    "argentina", "colombia", "chile", "peru", "uruguay", "costa rica",
    "indonesia", "malaysia", "thailand", "vietnam", "china", "taiwan",
    "hong kong", "south korea", "italy",
    # unambiguous foreign cities (avoid names shared with US cities)
    "london", "manchester", "edinburgh", "glasgow", "dublin", "cork",
    "berlin", "munich", "hamburg", "frankfurt", "paris", "amsterdam",
    "barcelona", "madrid", "lisbon", "porto", "warsaw", "krakow", "prague",
    "vienna", "zurich", "geneva", "stockholm", "oslo", "copenhagen",
    "helsinki", "brussels", "milan", "rome", "athens", "budapest",
    "bucharest", "sofia", "ljubljana", "kyiv", "istanbul", "dubai", "riyadh",
    "cairo", "nairobi", "lagos", "bengaluru", "bangalore", "hyderabad",
    "pune", "mumbai", "chennai", "gurgaon", "gurugram", "noida", "delhi",
    "toronto", "vancouver", "montreal", "ottawa", "calgary", "sydney",
    "melbourne", "brisbane", "tokyo", "seoul", "shanghai", "beijing",
    "taipei", "jakarta", "bangkok", "hanoi", "manila", "tel aviv",
    "bogota", "lima", "santiago", "guadalajara", "monterrey",
]
US_MARKERS = [
    "united states", "u.s.", "usa", "us-remote", "remote - us", "remote, us",
    "americas", "north america", "remote us", "us only", "anywhere in the us",
]

# 50 states + DC, for positively confirming US locations and for the state facet.
US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}
_NAME_TO_ABBR = {v.lower(): k for k, v in US_STATES.items()}
_ABBR_RE = re.compile(r"\b([A-Z]{2})\b")


def _has(text, terms):
    return any(t in text for t in terms)


def _matcher(terms):
    # Always require a leading word boundary. For SHORT tokens (<=3 chars, e.g.
    # 'soc', 'grc', 'ai') also require a trailing boundary so 'soc' matches
    # 'SOC Analyst' but not 'social'. For longer stems, leave the trailing side
    # open so 'threat intel' matches 'threat intelligence', 'threat hunt' matches
    # 'threat hunter', 'reverse engineer' matches 'reverse engineering', etc.
    terms = [t for t in terms if t]
    if not terms:
        return re.compile(r"(?!x)x")  # matches nothing
    short = [re.escape(t) for t in terms if len(t) <= 3]
    long = [re.escape(t) for t in terms if len(t) > 3]
    parts = []
    if long:
        parts.append("(?:" + "|".join(long) + ")")
    if short:
        parts.append("(?:" + "|".join(short) + r")(?!\w)")
    return re.compile(r"(?<!\w)(?:" + "|".join(parts) + r")", re.I)


_CLEAR_RE = _matcher(CLEARANCE_TERMS)
# Word-boundary match, not substring: bare 'Milwaukee' must not hit 'uk'.
_NON_US_RE = _matcher(NON_US_MARKERS)


def classify_location(loc, country):
    """Parse a free-text location into facets shared by the filter and dashboard.

    Returns (is_us, loc_type, states):
      is_us    True | False | None   (None = no US/non-US signal, e.g. bare "Remote")
      loc_type "remote" | "hybrid" | "onsite" | "unspecified"
      states   list of 2-letter US state codes found (may be empty)
    """
    l = (loc or "").lower().strip()
    c = (country or "").upper().strip()

    if "hybrid" in l:
        loc_type = "hybrid"
    elif "remote" in l or "distributed" in l or "anywhere" in l:
        loc_type = "remote"
    elif not l:
        loc_type = "unspecified"
    else:
        loc_type = "onsite"

    states = []
    for abbr in _ABBR_RE.findall(loc or ""):
        if abbr in US_STATES and abbr not in states:
            states.append(abbr)
    for name, abbr in _NAME_TO_ABBR.items():
        if name in l and abbr not in states:
            states.append(abbr)

    if c:
        is_us = c in ("US", "USA", "UNITED STATES", "U.S.", "U.S.A.")
    elif states or _has(l, US_MARKERS):
        is_us = True
    elif _NON_US_RE.search(l):
        is_us = False
    else:
        is_us = None
    return is_us, loc_type, states


def _us_ok(loc, country):
    """Return (ok, reason). USA only; unspecified is kept (user can judge)."""
    is_us, loc_type, _ = classify_location(loc, country)
    if is_us is False:
        where = loc or country or "?"
        return (False, f"remote outside US ({where})") if loc_type == "remote" \
            else (False, f"non-US ({where})")
    return True, ""


def _norm_titles(raw):
    """Strip parentheticals and split on '/' so a configured title like
    'Offensive Security Engineer / Penetration Tester' becomes two matchable
    phrases. Drop fragments shorter than 4 chars."""
    out = set()
    for t in raw or []:
        t = re.sub(r"\(.*?\)", "", t)
        for part in t.split("/"):
            p = part.strip().lower()
            if len(p) >= 4:
                out.add(p)
    return out


def build_scope(config, taxonomy):
    """Compile match terms (keywords + selected titles) and nontech drops.

    keywords / titles are kept separate so scoring can weight a title-phrase
    match above a generic keyword match.
    """
    subs = taxonomy.get("sub_sectors", {})
    keywords = set()
    for key in config.get("sub_sectors", []):
        for kw in (subs.get(key, {}).get("keywords", []) or []):
            keywords.add(kw.lower())
    titles = _norm_titles(config.get("titles", []))
    return {
        "titles": sorted(titles),
        "keywords": sorted(keywords),
        # Word-boundary matcher, not a substring test: plain `"soc" in blob`
        # matches "Associate" and "Social", dragging non-tech roles through
        # the gate on a keyword they don't actually contain.
        "match_re": _matcher(sorted(keywords | titles)),
        "nontech_drop": [t.lower() for t in taxonomy.get("nontech_drop", [])],
        "downrank_levels": {str(l).lower() for l in config.get("downrank_levels", []) or []},
        "exclude_levels": {str(l).lower() for l in config.get("exclude_levels", []) or []},
        "freshness": config.get("freshness", True),
        "max_yoe": int(config.get("max_yoe") or 0),
    }


def filter_jobs(jobs, scope):
    kept, dropped = [], []
    match_re = scope["match_re"]
    nontech = scope["nontech_drop"]
    for j in jobs:
        title = (j.get("title") or "").lower()
        desc = (j.get("description") or "").lower()
        blob = title + "\n" + desc

        if _has(title, nontech):
            dropped.append((j, "non-tech function (title)"))
            continue

        ok, reason = _us_ok(j.get("location"), j.get("country"))
        if not ok:
            dropped.append((j, reason))
            continue

        if _CLEAR_RE.search(blob):
            dropped.append((j, "requires security clearance"))
            continue

        if not match_re.search(blob):
            dropped.append((j, "off-target (no selected-sector keyword)"))
            continue

        kept.append(j)
    return kept, dropped
