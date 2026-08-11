"""Build a browsable HTML web app for a run and open it in the browser.

Reads runs/<DATE>/_run.json and renders a single self-contained page:
  - a stats header + a clickable STAGE STRIP (the application funnel)
  - a PIPELINE panel: a Sankey of how roles have moved between stages
  - a FILTER BAR of searchable multi-select dropdowns (one row, any facet)
  - a responsive GRID of role cards with per-card stage, note and applied date
  - companies that searched OK but matched nothing, then failed boards

Non-US roles are dropped from the grid (the search is USA-only); the count is
shown in the header so nothing silently disappears. Roles that are the same
title at the same company are merged into one card carrying every location.

CSS and JS live in dashboard_assets.py and are inlined verbatim — no build
step, no CDN, no network access required to open the result.

Usage:
    python scripts/build_dashboard.py            # latest run
    python scripts/build_dashboard.py 2026-08-10 # a specific date
    python scripts/build_dashboard.py --no-open  # build but don't open
"""
import datetime as dt
import html
import json
import re
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard_assets import CSS, JS  # noqa: E402
from filter import classify_location  # noqa: E402

SKILL_ROOT = Path(__file__).resolve().parent.parent
RUNS = SKILL_ROOT / "runs"
APPS_FILE = SKILL_ROOT / "applications.json"

TIER_COLOR = {"STRONG": "#1f9d55", "GOOD": "#b7791f", "MAYBE": "#6b7280"}
SOURCE_NAME = {"greenhouse": "Greenhouse", "lever": "Lever", "ashby": "Ashby",
               "smartrecruiters": "SmartRecruiters", "recruitee": "Recruitee"}
SENIOR_LEVELS = {"senior", "staff", "principal", "lead", "manager", "director", "vp", "head"}
LEVEL_ORDER = ["intern", "junior", "associate", "entry", "senior", "lead",
               "staff", "principal", "manager", "director", "vp", "head", "none"]

# The application funnel: (key, label, css var). Order is the funnel order and
# drives both the stage strip and the Sankey's column layout.
STAGES = [
    ("none", "Not applied", "--st-none"),
    ("applied", "Applied", "--st-applied"),
    ("screening", "Screening", "--st-screening"),
    ("interview", "Interview", "--st-interview"),
    ("offer", "Offer", "--st-offer"),
    ("accepted", "Accepted", "--st-accepted"),
    ("rejected", "Rejected", "--st-rejected"),
    ("ghosted", "No response", "--st-ghosted"),
]
PROGRESSION = ["none", "applied", "screening", "interview", "offer", "accepted"]
EXITS = ["rejected", "ghosted"]

# Title -> category. First match wins; order matters (specific before generic).
CATEGORIES = [
    ("Threat Intel", ["threat intel", "threat hunt", "cyber threat", "intelligence analyst"]),
    ("Offensive / Pentest", ["offensive", "penetration", "pentest", "red team", "exploit"]),
    ("AppSec / Product Sec", ["application security", "appsec", "product security"]),
    ("Cloud Security", ["cloud security"]),
    ("IR / Forensics", ["incident", "dfir", "forensic", "responder"]),
    ("Malware / RE", ["malware", "reverse engineer"]),
    ("GRC / Compliance", ["grc", "compliance", "governance", "risk", "audit"]),
    ("AI Security", ["ai security", "ml security"]),
    ("SOC / Detection", ["soc", "detection", "blue team", "security operations", "siem"]),
    ("Security Eng / Analyst", ["security engineer", "security analyst", "infosec",
                                "vulnerability", "security"]),
    ("Software Eng", ["software engineer", "backend", "back end", "frontend",
                      "front end", "full stack", "full-stack", "developer", "sde"]),
    ("Data / ML", ["data engineer", "data scientist", "machine learning", "ml engineer",
                   "ai engineer", "analytics", "data analyst", "applied scientist"]),
    ("DevOps / SRE", ["devops", "sre", "site reliability", "platform engineer",
                      "infrastructure", "cloud engineer"]),
    ("IT / Systems", ["sysadmin", "systems admin", "network engineer", "help desk",
                      "it support", "technical support", "desktop"]),
    ("Product / Design", ["product manager", "program manager", "designer", "ux", "ui"]),
    ("QA / Test", ["qa", "sdet", "test engineer", "quality", "automation engineer"]),
]
TYPE_LABEL = {"remote": "Remote", "hybrid": "Hybrid", "onsite": "On-site",
              "unspecified": "Unspecified"}
AGE_LABEL = {"7d": "Last 7 days", "30d": "8–30 days", "90d": "31–90 days",
             "old": "90+ days", "na": "Unknown"}
STALE_BUCKETS = ("90d", "old")
YOE_LABEL = {"0-2": "0–2 yrs", "3-5": "3–5 yrs", "6-8": "6–8 yrs",
             "9+": "9+ yrs", "na": "Unstated"}
SAL_LABEL = {"1": "Listed", "0": "Not listed"}
STALE_DAYS = 60
# A req we have personally watched stay open this long, or one that has been
# torn down and relisted, is very likely evergreen rather than a live opening.
GHOST_OPEN_DAYS = 45

FACETS = [
    ("status", "Stage"), ("type", "Type"), ("cat", "Category"), ("level", "Level"),
    ("yoe", "Experience"), ("age", "Posted"), ("sal", "Salary"), ("state", "State"),
    ("src", "Source"), ("company", "Company"),
]


def esc(s):
    return html.escape(str(s or ""))


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def norm_title(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def categorize(title):
    t = (title or "").lower()
    for label, kws in CATEGORIES:
        if any(k in t for k in kws):
            return label
    return "Other"


def enrich(j, source, run_date):
    """Attach derived facet fields to a job dict (mutates and returns it)."""
    is_us, loc_type, states = classify_location(j.get("location"), j.get("country"))
    j["_us"] = is_us
    j["_type"] = loc_type
    j["_states"] = states
    j["_cat"] = categorize(j.get("title"))
    j["_src"] = source
    age = j.get("age_days")
    if age is None and j.get("posted"):
        try:
            age = (run_date - dt.date.fromisoformat(j["posted"])).days
        except ValueError:
            pass
    j["_age"] = age
    j["_agebucket"] = ("na" if age is None else
                       "7d" if age <= 7 else "30d" if age <= 30 else
                       "90d" if age <= 90 else "old")
    yoe = j.get("yoe")
    j["_yoebucket"] = ("na" if not yoe else "0-2" if yoe <= 2 else
                       "3-5" if yoe <= 5 else "6-8" if yoe <= 8 else "9+")
    j["_ghost"] = bool(j.get("reposted")) or (j.get("open_days") or 0) >= GHOST_OPEN_DAYS
    if states:
        j["_region"] = ", ".join(states)
    elif loc_type in ("remote", "unspecified"):
        j["_region"] = "Remote / US"
    else:
        j["_region"] = j.get("location") or "US"
    return j


def merge_duplicates(jobs):
    """Collapse the same role posted once per location into a single card.

    Keyed on company + normalised title, so "Security Engineer" opened for
    Austin, NYC and Remote becomes one card carrying all three locations and
    the union of their states. The highest-scoring posting wins as the primary
    (its URL is the one Apply points at).
    """
    groups = {}
    for j in jobs:
        groups.setdefault((slug(j["comp"]), norm_title(j["title"])), []).append(j)
    out, merged = [], 0
    for g in groups.values():
        g.sort(key=lambda j: (-j["score"], j.get("_age") if j.get("_age") is not None else 999))
        primary = g[0]
        if len(g) > 1:
            merged += len(g) - 1
            locs, states = [], []
            for j in g:
                if j["_region"] and j["_region"] not in locs:
                    locs.append(j["_region"])
                for s in j["_states"]:
                    if s not in states:
                        states.append(s)
            primary["_dupes"] = len(g)
            primary["_locs"] = locs
            primary["_states"] = states
            primary["_ghost"] = primary["_ghost"] or any(j["_ghost"] for j in g)
        out.append(primary)
    return out, merged


def card(j):
    color = TIER_COLOR.get(j["tier"], "#6b7280")
    lvl = j.get("level", "")
    chips = ""
    if j.get("yoe"):
        chips += f'<span class="chip yoe">{j["yoe"]}+ yrs</span>'
    if lvl in SENIOR_LEVELS:
        chips += f'<span class="chip lvl">{esc(lvl)}</span>'
    if j.get("_dupes"):
        chips += f'<span class="chip loc">{j["_dupes"]} locations</span>'
    chips += "".join(f'<span class="chip">{esc(m)}</span>' for m in j.get("matched", [])[:3])

    badges = '<span class="new">NEW</span>' if j.get("new") else ""
    if j["_ghost"]:
        why = (f'relisted under {j["reposted"] + 1} posting ids'
               if j.get("reposted") else
               f'open at least {j.get("open_days", 0)} days')
        badges += f'<span class="ghost" title="Possible evergreen/ghost req: {esc(why)}">GHOST?</span>'

    age = j["_age"]
    if age is None:
        age_txt = ""
    elif age >= STALE_DAYS:
        age_txt = f' <span class="age stale">· {age}d ago</span>'
    else:
        age_txt = f' <span class="age">· {"today" if age <= 0 else str(age) + "d ago"}</span>'

    salary = j.get("salary") or ""
    sal_line = f'<div class="sal">{esc(salary)}</div>' if salary else ""
    region = ", ".join(j["_locs"][:3]) if j.get("_locs") else j["_region"]
    comp = j.get("comp") or ""
    search = esc((j["title"] + " " + comp + " " + j.get("location", "")).lower())
    opts = "".join(f'<option value="{k}">{esc(lab)}</option>' for k, lab, _ in STAGES)
    return f"""  <div class="card" data-id="{esc(j['id'])}" data-search="{search}" data-new="{int(bool(j.get('new')))}"
       data-type="{j['_type']}" data-level="{esc(lvl) or 'none'}" data-cat="{slug(j['_cat'])}"
       data-src="{j['_src']}" data-state="{' '.join(j['_states'])}"
       data-age="{j['_agebucket']}" data-sal="{int(bool(salary))}" data-yoe="{j['_yoebucket']}"
       data-ghost="{int(j['_ghost'])}" data-days="{age if age is not None else 9999}"
       data-status="none" data-company="{slug(comp)}" data-comp="{esc(comp.lower())}"
       data-title="{esc(j['title'])}" data-url="{esc(j['url'])}" data-score="{j['score']}">
    <div class="ctop">
      <span class="sc" style="color:{color};border-color:{color}">{j['score']}</span>
      <span class="tpill t-{j['_type']}">{TYPE_LABEL[j['_type']]}</span>{badges}
    </div>
    <a class="jt" href="{esc(j['url'])}" target="_blank" rel="noopener">{esc(j['title'])}</a>
    <div class="cco">{esc(comp)}</div>
    <div class="cloc">{esc(region)}{age_txt}</div>
    {sal_line}<div class="chips">{chips}</div>
    <a class="apply" href="{esc(j['url'])}" target="_blank" rel="noopener">Apply &rarr;</a>
    <div class="crow">
      <select class="stsel">{opts}</select>
      <button class="notebtn" title="Note and applied date">&#9998;</button>
    </div>
    <div class="notewrap hidden">
      <textarea class="ntext" placeholder="Notes — recruiter, referral, follow-up date…"></textarea>
      <input class="napp" type="date" title="Date applied">
    </div>
  </div>"""


def dropdown(field, label, options, order, labels):
    """One searchable multi-select facet. Options are re-rendered by JS on open,
    so the markup only needs the shell plus the ordering/label metadata."""
    return f"""    <div class="fdd" data-facet="{field}"
         data-order='{html.escape(json.dumps(order), quote=True)}'
         data-labels='{html.escape(json.dumps(labels), quote=True)}'>
      <button class="fddbtn">{esc(label)}<span class="cnt hidden">0</span><span class="car">&#9662;</span></button>
      <div class="fddmenu hidden">
        <input class="fddsearch" placeholder="Search {esc(label.lower())}&hellip;" autocomplete="off">
        <div class="fddlist"></div>
        <div class="fddfoot"><button class="fdd-all">Select all</button>
          <button class="fdd-none">Clear</button></div>
      </div>
    </div>"""


def build_filterbar(jobs):
    cnames = {slug(j["comp"]): j["comp"] for j in jobs if j.get("comp")}
    meta = {
        "status": ([k for k, _, _ in STAGES], {k: lab for k, lab, _ in STAGES}),
        "type": (["remote", "hybrid", "onsite", "unspecified"], TYPE_LABEL),
        "cat": ([], {slug(c): c for c, _ in CATEGORIES} | {"other": "Other"}),
        "level": (LEVEL_ORDER, {lv: lv.capitalize() for lv in LEVEL_ORDER} | {"none": "Unspecified"}),
        "yoe": (list(YOE_LABEL), YOE_LABEL),
        "age": (list(AGE_LABEL), AGE_LABEL),
        "sal": (["1", "0"], SAL_LABEL),
        "state": ([], {}),
        "src": ([], SOURCE_NAME),
        "company": ([], cnames),
    }
    return "\n".join(dropdown(f, lab, None, *meta[f]) for f, lab in FACETS)


def build_stage_strip():
    return "\n".join(
        f'    <div class="stg" data-stage="{k}" style="color:var({var})">'
        f'<span class="dot"></span><span class="n">0</span>'
        f'<span class="lbl">{esc(lab)}</span></div>'
        for k, lab, var in STAGES)


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Job Hunt — __DATE__</title>
<style>__CSS__</style></head>
<body>
<header>
  <h1>Job Hunt &mdash; __DATE__ &middot; USA &middot; tech</h1>
  <div class="stats">
    <div class="stat"><b id="stRoles">__JOBS__</b> roles</div>
    <div class="stat"><b id="stNew">__NEW__</b> new</div>
    <div class="stat"><b id="stCompanies">__COMPANIES__</b> companies</div>
    <div class="stat"><b id="stPipeline">0</b> in pipeline</div>
    <div class="stat"><b id="stGhost">0</b> possible ghosts</div>
    <div class="stat"><b>__MERGED__</b> merged</div>
    <div class="stat"><b>__NONUS__</b> non-US hidden</div>
    <div class="stat"><b>__FAILED__</b> boards failed</div>
  </div>
  <div class="stages">
__STAGESTRIP__
  </div>
  <div class="tools">
    <input id="q" placeholder="Search title, company, location…" autocomplete="off">
    <select id="sortSel" class="tbtn">
      <option value="score">Sort: score</option>
      <option value="age">Sort: newest posted</option>
      <option value="new">Sort: new first</option>
      <option value="company">Sort: company A–Z</option>
    </select>
    <button class="tbtn on" id="freshBtn">Fresh only (&le;30d)</button>
    <button class="tbtn" id="newBtn">New only</button>
    <button class="tbtn" id="ghostBtn">Ghosts only</button>
    <button class="tbtn" id="clrBtn">Clear filters</button>
    <button class="tbtn" id="expBtn">Export applications</button>
    <span id="shown"></span>
  </div>
</header>
<div class="filterbar">
__FILTERBAR__
</div>
<div class="pipe">
  <div class="pipe-h">
    <h2>Application pipeline</h2>
    <span class="sub" id="pipeSub">every role you have tracked, ignoring filters</span>
    <button class="tbtn" id="pipeScope" style="margin-left:auto">All applications</button>
    <button class="tbtn" id="pipeToggle">Hide</button>
  </div>
  <div id="pipeBody">
    <svg id="sankey" role="img" aria-label="Sankey diagram of application stages"></svg>
    <div class="pipe-empty hidden" id="pipeEmpty">
      Nothing tracked yet. Set a stage on any card &mdash; <b>Applied</b>, <b>Screening</b>,
      <b>Interview</b>, <b>Offer</b> &mdash; and this fills in with the flow between them,
      including where things drop out to <b>Rejected</b> or <b>No response</b>.
    </div>
  </div>
</div>
<div class="wrap">
  <div class="grid" id="grid">
__CARDS__
  </div>
  <div class="nomatch hidden" id="noMatch">No roles match these filters.</div>
__EMPTY__
__FAILEDSEC__
</div>
<div class="tip hidden" id="tip"></div>
<footer>Generated from runs/__DATE__/_run.json &middot; no applications are submitted
automatically &middot; you review and apply yourself.</footer>
<script>__JS__</script>
</body></html>
"""


def build(date=None, do_open=True):
    if date:
        run_dir = RUNS / date
    else:
        dirs = sorted([p for p in RUNS.iterdir() if p.is_dir()], reverse=True)
        if not dirs:
            print("no runs found")
            return 1
        run_dir = dirs[0]

    run_json = run_dir / "_run.json"
    if not run_json.exists():
        print(f"no _run.json in {run_dir}")
        return 1
    data = json.loads(run_json.read_text(encoding="utf-8"))
    companies = data["companies"]
    st = data.get("stats", {})
    try:
        run_date = dt.date.fromisoformat(data["date"])
    except (KeyError, ValueError):
        run_date = dt.date.today()

    jobs, non_us = [], 0
    for c in companies:
        if not (c["ok"] and c["jobs"]):
            continue
        for j in c["jobs"]:
            j["comp"] = c["name"]  # board-level company name
            enrich(j, c["source"], run_date)
            if j["_us"] is False:
                non_us += 1
                continue
            jobs.append(j)
    jobs, merged = merge_duplicates(jobs)
    jobs.sort(key=lambda j: (-j["score"], j["comp"].lower(), j["title"].lower()))

    empty = [c for c in companies if c["ok"] and not c["jobs"]]
    failed = [c for c in companies if not c["ok"]]

    apps = {}
    if APPS_FILE.exists():
        try:
            apps = json.loads(APPS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"warning: {APPS_FILE.name} is not valid JSON — ignoring it")

    empty_section = ""
    if empty:
        items = "\n".join(
            f'<div class="empty-co"><span class="coname-sm">{esc(c["name"])}</span>'
            f'<span class="src">{esc(SOURCE_NAME.get(c["source"], c["source"]))}</span>'
            f'<a href="{esc(c["careers_url"])}" target="_blank" rel="noopener">careers &nearr;</a></div>'
            for c in sorted(empty, key=lambda c: c["name"].lower()))
        empty_section = (f'<div class="section-h">Searched, no matching roles '
                         f'({len(empty)})</div>\n{items}')

    failed_section = ""
    if failed:
        items = "\n".join(
            f'<div class="failed-co"><span class="coname-sm">{esc(c["name"])}</span>'
            f'<span class="src">{esc(SOURCE_NAME.get(c["source"], c["source"]))}</span>'
            f'<span class="why">{esc(c["error"] or "could not fetch")}</span>'
            f'<a href="{esc(c["careers_url"])}" target="_blank" rel="noopener">open careers page &nearr;</a></div>'
            for c in sorted(failed, key=lambda c: c["name"].lower()))
        failed_section = (f'<div class="section-h">Could not search '
                          f'({len(failed)}) — check the careers page directly</div>\n{items}')

    js = (JS
          .replace("__CNAMES__", json.dumps({slug(j["comp"]): j["comp"] for j in jobs if j.get("comp")}))
          .replace("__STAGES__", json.dumps(STAGES))
          .replace("__PROGRESSION__", json.dumps(PROGRESSION))
          .replace("__EXITS__", json.dumps(EXITS))
          .replace("__FACET_DEFS__", json.dumps(FACETS))
          .replace("__STALE_BUCKETS__", json.dumps(list(STALE_BUCKETS)))
          .replace("__APPS__", json.dumps(apps)))

    page = (PAGE
            .replace("__CSS__", CSS)
            .replace("__FILTERBAR__", build_filterbar(jobs))
            .replace("__STAGESTRIP__", build_stage_strip())
            .replace("__CARDS__", "\n".join(card(j) for j in jobs))
            .replace("__EMPTY__", empty_section)
            .replace("__FAILEDSEC__", failed_section)
            .replace("__JOBS__", str(len(jobs)))
            .replace("__NEW__", str(sum(1 for j in jobs if j.get("new"))))
            .replace("__COMPANIES__", str(len({j["comp"] for j in jobs})))
            .replace("__MERGED__", str(merged))
            .replace("__NONUS__", str(non_us))
            .replace("__FAILED__", str(st.get("companies_failed", 0)))
            .replace("__JS__", js)
            .replace("__DATE__", esc(data["date"])))

    out = run_dir / "index.html"
    out.write_text(page, encoding="utf-8")
    ghosts = sum(1 for j in jobs if j["_ghost"])
    print(f"wrote {out} ({len(jobs)} roles, {merged} merged, {ghosts} possible ghosts, "
          f"{non_us} non-US hidden)")
    if do_open:
        webbrowser.open(out.resolve().as_uri())
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--no-open"]
    date = args[0] if args else None
    raise SystemExit(build(date, do_open="--no-open" not in sys.argv))
