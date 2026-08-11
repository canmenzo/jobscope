"""job-hunt orchestrator: fetch -> filter -> score -> group-by-company -> _run.json.

USA only, tech sector only. No resume/cover-letter generation. The output is a
machine-readable run file that build_dashboard.py turns into a browsable web app
(companies as branches, jobs underneath, failed boards listed at the bottom).

Config lives in config/config.yaml (written by setup — see SKILL.md). If it's
missing, this prints NEEDS_SETUP and exits 2 so the skill can run onboarding.

Run from the skill root:
    python scripts/job_hunt.py
    python scripts/job_hunt.py --limit 10          # cap companies (testing)
    python scripts/job_hunt.py --pick greenhouse:stripe,ashby:workos
    python scripts/job_hunt.py --new-only          # only roles unseen before
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

import yaml

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from fetch import board_url, fetch_all, hydrate_descriptions  # noqa: E402
from filter import build_scope, filter_jobs  # noqa: E402
from fit import blend, load_profile, score_fit  # noqa: E402
from score import score_all  # noqa: E402

CONFIG = SKILL_ROOT / "config"
RUNS = SKILL_ROOT / "runs"
SEEN_FILE = SKILL_ROOT / "seen_jobs.json"
SEEN_MAX_AGE_DAYS = 90  # prune seen entries not surfaced in this long

# "$140,000 - $180,000", "$140k–$180K", "$140,000 to $180,000".
# Sides must be comma-grouped, 4-7 plain digits, or k-suffixed — a bare "$175"
# (hourly/bonus noise) never matches.
_SAL_RE = re.compile(
    r"\$\s?(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{4,7}|\d{2,4}(?:\.\d+)?\s?[kK])"
    r"\s*(?:-|–|—|to)\s*"
    r"\$?\s?(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{4,7}|\d{2,4}(?:\.\d+)?\s?[kK])")


def _sal_low_usd(salary):
    """Lower bound of an extracted '$140K-$180K' string, in whole dollars."""
    m = re.search(r"\$(\d+)K", salary or "")
    return int(m.group(1)) * 1000 if m else 0


def _sal_k(s):
    s = s.lower().replace(",", "").replace(" ", "")
    return float(s[:-1]) if s.endswith("k") else float(s) / 1000


def extract_salary(desc):
    """First plausible annual USD range in the description, as '$140K–$180K'."""
    for m in _SAL_RE.finditer(desc or ""):
        lo, hi = _sal_k(m.group(1)), _sal_k(m.group(2))
        if 40 <= lo <= hi <= 1500:
            return f"${lo:.0f}K–${hi:.0f}K"
    return ""


# "5+ years of experience", "5-7 years ... experience", "minimum 3 years experience".
# Group 1 is the LOW end, so a range reports the actual bar, not the ceiling.
_YOE_RE = re.compile(
    r"(\d{1,2})\s*(?:\+|plus)?\s*(?:(?:-|–|—|to)\s*\d{1,2}\s*\+?)?\s*years?"
    r"[^.\n]{0,60}?\bexperience\b", re.I)

# A mention qualified by one of these is about a NICE-TO-HAVE or an adjacent
# skill ("2+ years with Terraform a plus"), not the role's actual bar.
_YOE_SOFT = re.compile(
    r"\b(preferred|preferably|nice to have|a plus|bonus|ideally|desirable|"
    r"advantage|familiarity)\b", re.I)


def extract_yoe(desc):
    """The role's real years-of-experience bar, or None.

    Takes the HIGHEST requirement among mentions that read as hard requirements,
    ignoring ones qualified as preferred/nice-to-have. An earlier version took
    the global minimum, which produced nonsense like a "Manager, Product
    Security Engineering" reading as a 1-year role because some adjacent skill
    deep in the description wanted "1+ year". Falling back to the minimum only
    when every mention is soft keeps genuinely junior postings from inflating.
    """
    hard, soft = [], []
    for m in _YOE_RE.finditer(desc or ""):
        y = int(m.group(1))
        if not 0 < y <= 20:
            continue
        window = (desc or "")[m.start(): m.end() + 60]
        (soft if _YOE_SOFT.search(window) else hard).append(y)
    if hard:
        return max(hard)
    return min(soft) if soft else None


# Visa sponsorship. Applying to a posting that says "we cannot sponsor" is pure
# wasted effort for anyone on a student or work visa, and the posting almost
# always says so plainly — it is just buried in the legal boilerplate.
#
# NEGATIVE is checked first and wins, because every negative phrasing contains
# a positive one ("not able to sponsor" contains "to sponsor"). Both patterns
# are deliberately narrow: a false "no" hides a real job, which is worse than
# leaving it unknown.
_SPONSOR_NO = re.compile(
    r"(?:"
    r"(?:not|unable|unwilling)\s+(?:be\s+)?(?:able\s+|willing\s+|in\s+a\s+position\s+)?"
    r"to\s+(?:provide\s+|offer\s+)?(?:visa\s+|immigration\s+)?sponsor"
    r"|do(?:es)?\s+not\s+(?:currently\s+)?(?:offer|provide|support)?\s*(?:visa\s+)?sponsor"
    r"|will\s+not\s+(?:be\s+)?(?:provide|offer|sponsor)"
    r"|no\s+(?:visa\s+|immigration\s+)?sponsorship"
    r"|without\s+(?:the\s+need\s+for\s+|any\s+need\s+for\s+|current\s+or\s+future\s+)?"
    r"(?:visa\s+|employer\s+)?sponsorship"
    r"|not\s+(?:be\s+)?eligible\s+for\s+(?:visa\s+)?sponsorship"
    r"|must\s+be\s+(?:a\s+)?(?:u\.?\s?s\.?|united\s+states)\s+citizen"
    r"|(?:u\.?\s?s\.?|united\s+states)\s+citizens?\s+(?:or|and)\s+(?:lawful\s+)?permanent\s+resident"
    r")", re.I)
_SPONSOR_YES = re.compile(
    r"(?:"
    r"(?:visa|h-?1b|immigration)\s+sponsorship\s+(?:is\s+)?(?:available|offered|provided)"
    r"|sponsorship\s+(?:is\s+)?(?:available|offered|provided)"
    r"|(?:will|do|can|happy\s+to|open\s+to|able\s+to|willing\s+to)\s+sponsor"
    r"|we\s+sponsor"
    r"|provide\s+(?:visa\s+|h-?1b\s+)?sponsorship"
    r"|eligible\s+for\s+(?:visa\s+)?sponsorship"
    r"|(?:opt|cpt|stem\s+opt)\s+(?:candidates|students)?\s*(?:are\s+)?welcome"
    r")", re.I)


def extract_sponsorship(desc):
    """'no' | 'yes' | '' for what a posting says about visa sponsorship."""
    text = desc or ""
    if _SPONSOR_NO.search(text):
        return "no"
    if _SPONSOR_YES.search(text):
        return "yes"
    return ""


def _norm_title(t):
    """Loose title key for spotting the same role twice: case/punctuation-free."""
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def annotate_history(jobs, seen, today):
    """Attach cross-run signals that a single snapshot can't show.

    first_seen / open_days — how long WE have watched this exact posting stay
    open, which is independent of (and more trustworthy than) the board's own
    posted date.
    reposted — the same company+title has appeared under a different posting id
    before. A req that keeps getting torn down and relisted is the classic
    ghost-job / evergreen-pipeline signature.
    """
    by_title = {}
    for jid, e in seen.items():
        key = ((e.get("company") or "").lower(), _norm_title(e.get("title")))
        by_title.setdefault(key, []).append((jid, e.get("first_seen", "")))

    for j in jobs:
        entry = seen.get(j["id"]) or {}
        first = entry.get("first_seen") or today
        j["first_seen"] = first
        try:
            j["open_days"] = (dt.date.fromisoformat(today)
                              - dt.date.fromisoformat(first)).days
        except ValueError:
            j["open_days"] = 0
        key = ((j.get("company") or "").lower(), _norm_title(j.get("title")))
        others = [i for i, _ in by_title.get(key, []) if i != j["id"]]
        j["reposted"] = len(others)
    return jobs


def log(msg):
    print(msg, flush=True)


def load_yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_seen():
    if SEEN_FILE.exists():
        try:
            return json.loads(SEEN_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(seen, indent=2), encoding="utf-8")


def resolve_companies(config, catalog, pick, limit):
    """Return an ordered list of {source, slug}."""
    if pick:
        out = []
        for tok in pick.split(","):
            tok = tok.strip()
            if ":" in tok:
                src, slug = tok.split(":", 1)
                out.append({"source": src.strip(), "slug": slug.strip()})
        return out

    chosen = config.get("companies", "all")
    if chosen == "all" or chosen is None:
        out = []
        for source, slugs in catalog.items():
            for slug in (slugs or []):
                out.append({"source": source, "slug": str(slug)})
    else:
        out = [{"source": c["source"], "slug": str(c["slug"])} for c in chosen]

    if limit and limit > 0:
        out = out[:limit]
    return out


def main():
    ap = argparse.ArgumentParser(description="USA tech job hunt")
    ap.add_argument("--min-score", type=int, default=None,
                    help="override min relevance score (default from config)")
    ap.add_argument("--limit", type=int, default=0,
                    help="cap number of companies fetched (testing)")
    ap.add_argument("--pick", type=str, default="",
                    help='override selection, e.g. "greenhouse:stripe,ashby:workos"')
    ap.add_argument("--new-only", action="store_true",
                    help="only include roles not seen on previous runs")
    args = ap.parse_args()

    cfg_path = CONFIG / "config.yaml"
    if not cfg_path.exists():
        log("NEEDS_SETUP")
        log("No config/config.yaml found. Run setup to choose sub-sectors, "
            "titles, and companies (see SKILL.md).")
        return 2

    config = load_yaml(cfg_path)
    taxonomy = load_yaml(CONFIG / "taxonomy.yaml")
    profile_path = CONFIG / "profile.yaml"
    profile = load_profile(load_yaml(profile_path)) if profile_path.exists() else None
    catalog = load_yaml(CONFIG / "companies_catalog.yaml")
    min_score = args.min_score if args.min_score is not None \
        else int(config.get("min_score", 55))

    companies = resolve_companies(config, catalog, args.pick, args.limit)
    scope = build_scope(config, taxonomy)
    scope["today"] = dt.date.today()
    seen = load_seen()

    log("== job-hunt (USA · tech) ==")
    log(f"sub-sectors: {', '.join(config.get('sub_sectors', [])) or '(none)'}")
    log(f"titles: {', '.join(config.get('titles', [])) or '(none)'}")
    log(f"companies: {len(companies)}   min-score: {min_score}")
    log("profile: " + (f"{profile['years']:g} yrs, targeting "
                       f"{'/'.join(profile['target_levels'])}, "
                       f"{len(profile['skills'])} skills"
                       if profile else "none — scoring on relevance only"))

    log("\n[1/4] Fetching postings...")
    jobs, statuses = fetch_all(companies, log, config.get("workday_search") or None)
    log(f"  total postings pulled: {len(jobs)}")

    log("\n[2/4] Filtering (USA + selected sectors)...")
    kept, dropped = filter_jobs(jobs, scope)
    # Workday's list endpoint carries no description, so those postings clear
    # the first gate on their title alone. Fetch the real text for survivors
    # and re-run the gate — otherwise clearance-required roles slip through and
    # nothing downstream (years-of-experience, salary, skills) has text to read.
    pending = [j for j in kept if j.get("detail_url")]
    if pending:
        hydrate_descriptions(pending, log)
        rekept, redropped = filter_jobs(pending, scope)
        survived = {j["id"] for j in rekept}
        kept = [j for j in kept if not j.get("detail_url") or j["id"] in survived]
        dropped += redropped
    log(f"  kept: {len(kept)}   dropped: {len(dropped)}")
    reasons = {}
    for _, r in dropped:
        key = r.split("(")[0].strip()
        reasons[key] = reasons.get(key, 0) + 1
    for r, n in sorted(reasons.items(), key=lambda x: -x[1]):
        log(f"    - {n:5} {r}")

    log("\n[3/4] Scoring relevance...")
    for j in kept:
        j["yoe"] = extract_yoe(j.get("description", ""))
    scored = score_all(kept, scope)
    scored = [j for j in scored if j["score"] >= min_score]
    for j in scored:
        j["salary"] = extract_salary(j.get("description", ""))
        j["salary_low"] = _sal_low_usd(j["salary"])
        j["sponsorship"] = extract_sponsorship(j.get("description", ""))
    if profile:
        for j in scored:
            j["relevance"] = j["score"]
            j["fit"], j["fit_reasons"] = score_fit(j, profile)
            j["score"] = blend(j["relevance"], j["fit"])
        scored.sort(key=lambda j: -j["score"])
    n_new = sum(1 for j in scored if j["id"] not in seen)
    for j in scored:
        j["new"] = j["id"] not in seen
    if args.new_only:
        scored = [j for j in scored if j["new"]]
    date = dt.date.today().isoformat()
    annotate_history(scored, seen, date)
    n_repost = sum(1 for j in scored if j["reposted"])
    log(f"  >= {min_score}: {len(scored)} roles ({n_new} new, {n_repost} relisted)")

    log("\n[4/4] Grouping by company + writing run file...")
    by_slug = {}
    for j in scored:
        by_slug.setdefault((j["source"], j["slug"]), []).append(j)

    companies_out = []
    for st in statuses:
        key = (st["source"], st["slug"])
        roles = sorted(by_slug.get(key, []), key=lambda j: j["score"], reverse=True)
        companies_out.append({
            "name": st["name"], "source": st["source"], "slug": st["slug"],
            "ok": st["ok"], "error": st["error"],
            "careers_url": st["careers_url"] or board_url(st["source"], st["slug"]),
            "postings": st["count"], "match_count": len(roles),
            "jobs": [{
                "id": j["id"], "title": j["title"], "location": j.get("location", ""),
                "url": j["url"], "score": j["score"],
                "tier": j["tier"], "level": j.get("level", ""),
                "matched": j.get("matched", []), "new": j["new"],
                "posted": j.get("posted", ""), "age_days": j.get("age_days"),
                "salary": j.get("salary", ""), "yoe": j.get("yoe"),
                "sponsorship": j.get("sponsorship", ""),
                "relevance": j.get("relevance", j["score"]),
                "fit": j.get("fit"), "fit_reasons": j.get("fit_reasons", []),
                "first_seen": j.get("first_seen", ""),
                "open_days": j.get("open_days", 0),
                "reposted": j.get("reposted", 0),
            } for j in roles],
        })

    # Sort: companies with matches first (by best score), then ok-but-no-match,
    # then failed boards last.
    def sort_key(c):
        if not c["ok"]:
            return (2, 0)
        if not c["jobs"]:
            return (1, 0)
        return (0, -c["jobs"][0]["score"])
    companies_out.sort(key=sort_key)

    run_dir = RUNS / date
    run_dir.mkdir(parents=True, exist_ok=True)

    ok = [c for c in companies_out if c["ok"]]
    failed = [c for c in companies_out if not c["ok"]]
    run = {
        "date": date, "country": "US",
        "sub_sectors": config.get("sub_sectors", []),
        "titles": config.get("titles", []),
        "min_score": min_score,
        "stats": {
            "companies_total": len(companies_out),
            "companies_ok": len(ok),
            "companies_failed": len(failed),
            "companies_with_jobs": sum(1 for c in ok if c["jobs"]),
            "jobs_total": len(scored),
            "jobs_new": sum(1 for j in scored if j.get("new")),
        },
        "companies": companies_out,
    }
    (run_dir / "_run.json").write_text(json.dumps(run, indent=2), encoding="utf-8")

    # mark surfaced roles as seen; prune entries not surfaced in 90 days
    for j in scored:
        entry = seen.get(j["id"]) or {"first_seen": date, "company": j["company"],
                                      "title": j["title"], "url": j["url"]}
        entry["last_seen"] = date
        seen[j["id"]] = entry
    cutoff = (dt.date.today() - dt.timedelta(days=SEEN_MAX_AGE_DAYS)).isoformat()
    seen = {k: v for k, v in seen.items()
            if v.get("last_seen", v.get("first_seen", date)) >= cutoff}
    save_seen(seen)

    log(f"\n  {run['stats']['companies_with_jobs']} companies with matches · "
        f"{len(scored)} roles · {len(failed)} boards failed")
    log(f"Run file: {run_dir / '_run.json'}")
    log("Next: python scripts/build_dashboard.py   (builds + opens the web app)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
