"""Relevance scoring (0-100) of a job against the user's selected titles + keywords.

No resume profile — relevance is purely "how well does this posting match what the
user asked to search for."

Design (deliberately discriminating, not buzzword-counting):
  * A selected TITLE PHRASE in the job title is the strongest signal. The score
    scales with COVERAGE — how much of the title actually IS the target phrase.
    "Detection Engineer" matching "Detection Engineer" ~= full coverage -> ~95.
    "Detection" buried in "Staff Frontend Full Stack Software Engineer" -> low
    coverage -> ~80s, so a verbose senior title can't out-rank a clean match.
  * A sub-sector KEYWORD in the title (but no named title) -> right area, mid score.
  * A match only in the description -> weak.
Counting more keywords does NOT inflate the score.

Tiers (for dashboard coloring): STRONG >=80 | GOOD 62-79 | MAYBE <62.
A seniority level (senior/staff/principal/...) is detected and surfaced for the
UI. By default it does NOT change the score, but config can opt in:
  downrank_levels: [staff, principal, ...]  -> -25 relevance for those levels
  exclude_levels:  [director, vp, ...]      -> scored 0 (dropped by min_score)

Two more penalties keep unapplyable roles off the top of the grid:
  * FRESHNESS — a req sitting open for months is usually filled or a ghost
    posting. Score decays from STALE_START days to a floor at STALE_FULL.
    Disable with `freshness: false` in config.
  * YEARS OF EXPERIENCE — `max_yoe: N` in config downranks postings that ask
    for meaningfully more than N years.
"""
import datetime as dt
import re

LEVEL_PENALTY = 25

# Freshness decay: no penalty for the first STALE_START days, ramping linearly
# to the full STALE_MAX by STALE_FULL days old.
STALE_START, STALE_FULL, STALE_MAX = 21, 150, 22

# Over-qualified gate: points lost per year demanded above config's max_yoe.
YOE_PENALTY_PER_YEAR, YOE_PENALTY_MAX = 5, 20

# Checked in priority order (principal before senior, etc.).
LEVELS = [
    ("principal", "principal"), ("distinguished", "principal"),
    ("director", "director"), ("vice president", "vp"), ("head of", "head"),
    ("staff", "staff"), ("manager", "manager"), ("lead", "lead"),
    ("senior", "senior"), ("sr.", "senior"), ("sr ", "senior"),
    ("intern", "intern"), ("junior", "junior"), ("jr.", "junior"),
    ("entry level", "entry"), ("associate", "associate"),
]


def _matcher(terms):
    # See filter._matcher: leading boundary always; trailing boundary only for
    # short tokens (<=3 chars) so 'soc' won't match 'social' while longer stems
    # like 'threat intel' still match 'threat intelligence'.
    terms = [t for t in terms if t]
    if not terms:
        return None
    short = [re.escape(t) for t in terms if len(t) <= 3]
    long = [re.escape(t) for t in terms if len(t) > 3]
    parts = []
    if long:
        parts.append("(?:" + "|".join(long) + ")")
    if short:
        parts.append("(?:" + "|".join(short) + r")(?!\w)")
    return re.compile(r"(?<!\w)(?:" + "|".join(parts) + r")", re.I)


def _distinct(rx, text):
    if not rx or not text:
        return set()
    return {m.lower() for m in rx.findall(text)}


def _level(title_l):
    for needle, label in LEVELS:
        if needle in title_l:
            return label
    return ""


def age_days(posted, today):
    """Days between a YYYY-MM-DD posted date and `today`; None if unparseable."""
    if not posted or not today:
        return None
    try:
        return max(0, (today - dt.date.fromisoformat(str(posted)[:10])).days)
    except ValueError:
        return None


def _age_penalty(days):
    if days is None or days <= STALE_START:
        return 0
    ramp = (days - STALE_START) / (STALE_FULL - STALE_START)
    return round(STALE_MAX * min(1.0, ramp))


def _yoe_penalty(yoe, max_yoe):
    if not yoe or not max_yoe or yoe <= max_yoe:
        return 0
    return min(YOE_PENALTY_MAX, (yoe - max_yoe) * YOE_PENALTY_PER_YEAR)


def score_job(job, scope):
    title = job.get("title") or ""
    desc = job.get("description") or ""
    title_l, desc_l = title.lower(), desc.lower()

    titles = [t for t in scope.get("titles", []) if t]
    rx_kw = _matcher(scope.get("keywords", []))

    phrase_hits = [t for t in titles if t in title_l]
    kw_in_title = _distinct(rx_kw, title)

    if phrase_hits:
        best = max(phrase_hits, key=len)
        coverage = len(best) / max(len(title_l.strip()), 1)
        score = 72 + round(min(23, coverage * 28))
    elif kw_in_title:
        score = 55 + min(8, (len(kw_in_title) - 1) * 3)
    elif rx_kw and rx_kw.search(desc) or any(t in desc_l for t in titles):
        score = 42
    else:
        score = 0

    level = _level(title_l)
    if level and level in scope.get("exclude_levels", ()):
        score = 0
    elif level and level in scope.get("downrank_levels", ()):
        score -= LEVEL_PENALTY

    days = age_days(job.get("posted"), scope.get("today"))
    job["age_days"] = days
    if score > 0:
        if scope.get("freshness", True):
            score -= _age_penalty(days)
        score -= _yoe_penalty(job.get("yoe"), scope.get("max_yoe"))

    score = max(0, min(100, score))
    tier = "STRONG" if score >= 80 else "GOOD" if score >= 62 else "MAYBE"

    matched = sorted(kw_in_title | _distinct(rx_kw, desc) | set(phrase_hits))
    job["score"] = score
    job["tier"] = tier
    job["level"] = level
    job["matched"] = matched[:6]
    return job


def score_all(jobs, scope):
    return [score_job(j, scope) for j in jobs]
