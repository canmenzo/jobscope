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

from fetch import board_url, fetch_all  # noqa: E402
from filter import build_scope, filter_jobs  # noqa: E402
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


def extract_yoe(desc):
    """Lowest years-of-experience requirement stated in the description.

    Deliberately the MINIMUM across all mentions: a posting saying "3+ years
    required, 8+ preferred" has a real bar of 3, and under-reporting keeps
    reachable roles visible rather than penalizing them.
    """
    years = [int(m.group(1)) for m in _YOE_RE.finditer(desc or "")]
    years = [y for y in years if 0 < y <= 20]
    return min(years) if years else None


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

    log("\n[1/4] Fetching postings...")
    jobs, statuses = fetch_all(companies, log)
    log(f"  total postings pulled: {len(jobs)}")

    log("\n[2/4] Filtering (USA + selected sectors)...")
    kept, dropped = filter_jobs(jobs, scope)
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
