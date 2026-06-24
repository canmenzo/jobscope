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
import sys
from pathlib import Path

import yaml

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from fetch import fetch_all, board_url      # noqa: E402
from filter import filter_jobs, build_scope  # noqa: E402
from score import score_all                  # noqa: E402

CONFIG = SKILL_ROOT / "config"
RUNS = SKILL_ROOT / "runs"
SEEN_FILE = SKILL_ROOT / "seen_jobs.json"


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
    scored = score_all(kept, scope)
    scored = [j for j in scored if j["score"] >= min_score]
    n_new = sum(1 for j in scored if j["id"] not in seen)
    for j in scored:
        j["new"] = j["id"] not in seen
    if args.new_only:
        scored = [j for j in scored if j["new"]]
    log(f"  >= {min_score}: {len(scored)} roles ({n_new} new)")

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
                "url": j["url"], "comp": j.get("comp", ""), "score": j["score"],
                "tier": j["tier"], "level": j.get("level", ""),
                "matched": j.get("matched", []), "new": j["new"],
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

    date = dt.date.today().isoformat()
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

    # mark surfaced roles as seen
    for j in scored:
        seen[j["id"]] = {"first_seen": date, "company": j["company"],
                         "title": j["title"], "url": j["url"]}
    save_seen(seen)

    log(f"\n  {run['stats']['companies_with_jobs']} companies with matches · "
        f"{len(scored)} roles · {len(failed)} boards failed")
    log(f"Run file: {run_dir / '_run.json'}")
    log("Next: python scripts/build_dashboard.py   (builds + opens the web app)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
