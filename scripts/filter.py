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
    "emea", "apac", "uk", "united kingdom", "england", "ireland", "india",
    "germany", "berlin", "munich", "canada", "toronto", "vancouver", "australia",
    "sydney", "singapore", "europe", "european", "latam", "poland", "warsaw",
    "spain", "madrid", "barcelona", "france", "paris", "netherlands", "amsterdam",
    "brazil", "mexico", "japan", "tokyo", "philippines", "romania", "portugal",
    "lisbon", "israel", "tel aviv", "switzerland", "sweden", "norway", "denmark",
    "south africa", "new zealand", "argentina", "colombia", "costa rica", "dublin",
]
US_MARKERS = [
    "united states", "u.s.", "usa", "us-remote", "remote - us", "remote, us",
    "americas", "north america", "remote us", "us only", "anywhere in the us",
]


def _has(text, terms):
    return any(t in text for t in terms)


def _matcher(terms):
    # Leading word boundary only: 'detection' matches 'detections' and
    # 'threat intel' matches 'threat intelligence', while 'soc' still won't
    # match inside 'associate' (preceded by a word char).
    pat = "|".join(re.escape(t) for t in terms)
    return re.compile(r"(?<!\w)(?:" + pat + r")", re.I)


_CLEAR_RE = _matcher(CLEARANCE_TERMS)


def _us_ok(loc, country):
    """Return (ok, reason). USA only."""
    c = (country or "").upper()
    if c:
        if c in ("US", "USA", "UNITED STATES"):
            return True, ""
        return False, f"non-US ({loc or c})"
    l = (loc or "").lower().strip()
    if not l:
        return True, ""  # unspecified — keep, Claude/user can judge
    is_remote = "remote" in l or "distributed" in l
    has_non_us = _has(l, NON_US_MARKERS)
    has_us = _has(l, US_MARKERS)
    if has_non_us and not has_us:
        return (False, f"remote outside US ({loc})") if is_remote \
            else (False, f"non-US ({loc})")
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
        "match_terms": sorted(keywords | titles),
        "nontech_drop": [t.lower() for t in taxonomy.get("nontech_drop", [])],
    }


def filter_jobs(jobs, scope):
    kept, dropped = [], []
    match_terms = scope["match_terms"]
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

        if not _has(blob, match_terms):
            dropped.append((j, "off-target (no selected-sector keyword)"))
            continue

        kept.append(j)
    return kept, dropped
