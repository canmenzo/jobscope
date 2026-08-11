"""Build a browsable HTML web app for a run and open it in the browser.

Reads runs/<DATE>/_run.json and renders one self-contained page with two tabs:

  BOARD — a dense sortable LIST of every matching role on the left, and a
          drag-and-drop KANBAN on the right (Applied / Screening / Interview /
          Offer, plus a closed strip for Accepted / Rejected / No response).
          Drag a row onto a column to move it through your pipeline; drag it
          back onto the list to untrack it.
  FLOW  — a full-width Sankey of how roles actually moved between stages, with
          a conversion-rate strip above it.

Non-US roles are dropped (the search is USA-only); the count is shown so
nothing silently disappears. The same title at the same company across cities
is merged into one row carrying every location.

CSS and JS live in dashboard_assets.py and are inlined verbatim — no build
step, no CDN, no network access required to open the result.

Usage:
    python scripts/build_dashboard.py            # latest run
    python scripts/build_dashboard.py 2026-08-11 # a specific date
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

SOURCE_NAME = {"greenhouse": "Greenhouse", "lever": "Lever", "ashby": "Ashby",
               "smartrecruiters": "SmartRecruiters", "recruitee": "Recruitee",
               "workday": "Workday"}
LEVEL_ORDER = ["intern", "junior", "associate", "entry", "senior", "lead",
               "staff", "principal", "manager", "director", "vp", "head", "none"]

# (key, label, css var). Order is the funnel order.
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
BOARD_STAGES = ["applied", "screening", "interview", "offer"]   # kanban columns
CLOSED_STAGES = ["accepted", "rejected", "ghosted"]             # closed strip

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
GHOST_OPEN_DAYS = 45

SCORE_TIP = (
    "How good this role is FOR YOU, 0-100. Blends two things: relevance "
    "(does it match the titles and keywords you are searching for) and fit "
    "(could you realistically get it — years of experience asked for vs yours, "
    "the level of the title, how much of your toolkit it names, and whether the "
    "posted pay band sits above you). Fit carries the larger share. "
    "Hover a score to see what pulled that one down. "
    "Add config/profile.yaml to switch fit on; without it this is relevance only."
)

# Facets shown as their own button; everything else lives under "More".
PRIMARY_FACETS = ["status", "type", "cat"]
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
    for lab, kws in CATEGORIES:
        if any(k in t for k in kws):
            return lab
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
    """Collapse the same role posted once per location into a single entry.

    Keyed on company + normalised title, so "Security Engineer" opened for
    Austin, NYC and Remote becomes one row carrying all three locations and the
    union of their states. The highest-scoring posting wins as the primary.
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


def sal_num(s):
    """Lower bound of an extracted '$140K–$180K' range, for sorting."""
    m = re.search(r"\$(\d+)K", s or "")
    return int(m.group(1)) if m else -1


def age_text(j):
    a = j["_age"]
    return "—" if a is None else ("today" if a <= 0 else f"{a}d")


def region_text(j):
    return ", ".join(j["_locs"][:2]) if j.get("_locs") else j["_region"]


def row(j):
    if j.get("fit") is None:
        score_tip = ""
    else:
        why = "; ".join(j.get("fit_reasons") or []) or "nothing holding it back"
        score_tip = (f' data-tip="<b>Relevance {j.get("relevance", j["score"])}'
                     f' &middot; Fit {j["fit"]}</b><br>{esc(why)}"')
    badges = ""
    if j.get("new"):
        badges += '<span class="tag new">NEW</span>'
    if j["_ghost"]:
        why = (f'relisted under {j["reposted"] + 1} posting ids' if j.get("reposted")
               else f'open at least {j.get("open_days", 0)} days')
        badges += f'<span class="tag ghost" title="Possible evergreen req: {esc(why)}">GHOST</span>'
    if j.get("_dupes"):
        badges += f'<span class="tag loc" title="{esc(" · ".join(j["_locs"]))}">{j["_dupes"]} LOC</span>'
    age = j["_age"]
    stale = " stale" if age is not None and age >= STALE_DAYS else ""
    return f"""  <div class="row" draggable="true" data-id="{esc(j['id'])}"
       data-search="{esc((j['title'] + ' ' + j['comp'] + ' ' + j.get('location', '')).lower())}"
       data-new="{int(bool(j.get('new')))}" data-ghost="{int(j['_ghost'])}"
       data-type="{j['_type']}" data-level="{esc(j.get('level') or 'none')}"
       data-cat="{slug(j['_cat'])}" data-src="{j['_src']}" data-state="{' '.join(j['_states'])}"
       data-age="{j['_agebucket']}" data-sal="{int(bool(j.get('salary')))}"
       data-yoe="{j['_yoebucket']}" data-company="{slug(j['comp'])}"
       data-score="{j['score']}" data-days="{age if age is not None else 9999}"
       data-salnum="{sal_num(j.get('salary'))}" data-ttl="{esc(j['title'].lower())}"
       data-comp="{esc(j['comp'].lower())}" data-loc="{esc(region_text(j).lower())}">
    <div class="sc"{score_tip}>{j['score']}</div>
    <div class="rt"><a href="{esc(j['url'])}" target="_blank" rel="noopener">{esc(j['title'])}</a>{badges}</div>
    <div class="rc">{esc(j['comp'])}</div>
    <div class="rl">{esc(region_text(j))}</div>
    <div class="ra{stale}">{age_text(j)}</div>
    <div class="rs">{esc(j.get('salary') or '—')}</div>
    <div class="racts">
      <button class="iact" data-act="open" title="Open posting">&#8599;</button>
      <button class="iact" data-act="apply" title="Move to Applied">&#43;</button>
    </div>
  </div>"""


def facet_meta(jobs):
    """{field: {order, labels}} for every facet, emitted once as a JS global.

    Deliberately NOT stored per-dropdown in the DOM: the facets grouped under
    "More" have no element of their own, so a DOM lookup returned null and
    silently emptied that entire menu.
    """
    cnames = {slug(j["comp"]): j["comp"] for j in jobs if j.get("comp")}
    labels = {
        "status": {k: lab for k, lab, _ in STAGES},
        "type": TYPE_LABEL,
        "cat": {slug(c): c for c, _ in CATEGORIES} | {"other": "Other"},
        "level": {lv: lv.capitalize() for lv in LEVEL_ORDER} | {"none": "Unspecified"},
        "yoe": YOE_LABEL, "age": AGE_LABEL, "sal": SAL_LABEL,
        "state": {}, "src": SOURCE_NAME, "company": cnames,
    }
    order = {
        "status": [k for k, _, _ in STAGES], "type": list(TYPE_LABEL),
        "level": LEVEL_ORDER, "yoe": list(YOE_LABEL), "age": list(AGE_LABEL),
        "sal": ["1", "0"], "cat": [], "state": [], "src": [], "company": [],
    }
    return {f: {"order": order.get(f, []), "labels": labels.get(f, {})}
            for f, _ in FACETS}


def dropdown(btn_label, fields, tip, align=""):
    """A searchable multi-select. One field = a single facet; several = the
    grouped "More" menu."""
    single = fields[0] if len(fields) == 1 else ""
    data_single = f'data-facet="{single}"' if single else ""
    return f"""    <div class="fdd" {data_single}
         data-fields='{html.escape(json.dumps(fields), quote=True)}' data-align="{align}">
      <button class="fbtn" data-tip="{esc(tip)}">{esc(btn_label)}<span class="n hidden">0</span><span class="car">&#9662;</span></button>
    </div>"""


FACET_TIPS = {
    "status": "Where each role sits in your pipeline",
    "type": "Remote, hybrid or on-site",
    "cat": "Role family, derived from the job title",
}


def build_filters():
    out = [dropdown(lab, [f], FACET_TIPS.get(f, lab))
           for f, lab in FACETS if f in PRIMARY_FACETS]
    rest = [f for f, _ in FACETS if f not in PRIMARY_FACETS]
    names = ", ".join(dict(FACETS)[f] for f in rest)
    out.append(dropdown("More", rest, f"More filters: {names}", align="right"))
    return "\n".join(out)


def build_columns():
    cols = []
    for k in BOARD_STAGES:
        lab = dict((s[0], s[1]) for s in STAGES)[k]
        var = dict((s[0], s[2]) for s in STAGES)[k]
        cols.append(f"""      <div class="col" id="dz-{k}">
        <div class="ch"><span class="sw" style="background:var({var})"></span>{esc(lab)}
          <span class="cn" id="cn-{k}">0</span></div>
        <div class="cb" id="cb-{k}"></div>
      </div>""")
    return "\n".join(cols)


def build_closed():
    out = []
    for k in CLOSED_STAGES:
        lab = dict((s[0], s[1]) for s in STAGES)[k]
        var = dict((s[0], s[2]) for s in STAGES)[k]
        out.append(f'<div class="cl" id="dz-{k}"><span class="sw" style="background:var({var})">'
                   f'</span><b id="cn-{k}">0</b> {esc(lab)}</div>')
    return "\n".join(out)


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Jobscope — __DATE__</title>
<style>__CSS__</style></head>
<body>
<div class="app">
  <div class="top">
    <div class="brand">Jobscope</div>
    <div class="kpi">
      <span data-tip="Roles passing the filters you have set right now"><b id="shown">0</b> shown</span>
      <span data-tip="Every role this run matched, before filtering"><b>__JOBS__</b> roles</span>
      <span data-tip="Distinct companies across those roles"><b>__COMPANIES__</b> companies</span>
      <span data-tip="Roles you have moved onto the board (Applied and beyond)"><b id="kTracked">0</b> tracked</span>
      <span class="warn" data-tip="<b>Possible ghost jobs.</b> The req has stayed open unusually long, or the same title keeps getting reposted under a new id. Often an evergreen pipeline rather than a live opening.">
        <b>__GHOSTS__</b> ghosts</span>
      <span data-tip="<b>Duplicate rows folded together.</b> The same title at the same company posted once per city becomes one row carrying every location"><b>__MERGED__</b> merged</span>
    </div>
    <div class="tabs">
      <button class="tab on" data-view="board">Board</button>
      <button class="tab" data-view="flow">Flow</button>
    </div>
    <div class="live"><span class="dot"></span>__DATE__ &middot; USA &middot; Tech</div>
  </div>

  <div class="main">
    <div class="listpane" id="listpane">
      <div class="filters">
        <input class="search" id="q" placeholder="Search title, company, location…  ( / )" autocomplete="off">
        <button class="fbtn on" id="freshBtn" data-tip="Hide anything posted more than 30 days ago. Long-open reqs are usually filled or were never real.">Fresh <span class="n">30d</span></button>
__FILTERS__
        <button class="fbtn" id="newBtn" data-tip="Only roles that were not present on any previous run">New</button>
        <button class="fbtn" id="ghostBtn" data-tip="Hide roles flagged as possible ghost jobs — open unusually long, or the same title repeatedly relisted under a new id.">Hide ghosts</button>
        <button class="fbtn" id="clrBtn" data-tip="Clear the search and every active filter">Reset</button>
      </div>
      <div class="lhead">
        <span data-sort="score" class="sorted" data-tip="__SCORETIP__">Score</span>
        <span data-sort="title">Role</span>
        <span data-sort="company">Company</span>
        <span data-sort="location">Location</span>
        <span data-sort="age" style="text-align:right">Age</span>
        <span data-sort="salary" style="text-align:right">Salary</span>
      </div>
      <div class="rows" id="rows">
__ROWS__
      </div>
      <div class="empty-list hidden" id="emptyList">No roles match these filters.</div>
    </div>

    <div class="right">
      <div class="board" id="viewBoard">
        <div class="cols">
__COLUMNS__
        </div>
        <div class="closed">
          <span class="lab">Closed</span>
__CLOSED__
          <span class="hint">drag a card here to close it out</span>
        </div>
      </div>

      <div class="flow hidden" id="viewFlow">
        <div class="funnel" id="funnel"></div>
        <div class="flowbox" id="flowbox">
          <h2>Stage flow</h2>
          <div class="sub">every role you have tracked &middot; hover a ribbon for exact counts</div>
          <svg id="sankey" role="img" aria-label="Sankey diagram of application stages"></svg>
          <div class="flow-empty hidden" id="flowEmpty">
            Nothing tracked yet.<br>Drag a role from the list onto <b>Applied</b> on the Board tab,
            then move it along as things progress —<br>this fills in with the flow between stages,
            including where things drop out.
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
<div class="tip hidden" id="tip"></div>
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
    try:
        run_date = dt.date.fromisoformat(data["date"])
    except (KeyError, ValueError):
        run_date = dt.date.today()

    jobs, non_us = [], 0
    for c in data["companies"]:
        if not (c["ok"] and c["jobs"]):
            continue
        for j in c["jobs"]:
            j["comp"] = c["name"]
            enrich(j, c["source"], run_date)
            if j["_us"] is False:
                non_us += 1
                continue
            jobs.append(j)
    jobs, merged = merge_duplicates(jobs)
    jobs.sort(key=lambda j: (-j["score"], j["comp"].lower(), j["title"].lower()))

    apps = {}
    if APPS_FILE.exists():
        try:
            apps = json.loads(APPS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"warning: {APPS_FILE.name} is not valid JSON — ignoring it")

    # Compact job index the JS builds kanban cards from, so a tracked role still
    # renders on the board while filtered out of the list.
    jobs_js = {j["id"]: {"title": j["title"], "comp": j["comp"], "url": j["url"],
                         "region": region_text(j), "age": age_text(j),
                         "salary": j.get("salary") or "", "score": j["score"]}
               for j in jobs}

    js = (JS
          .replace("__JOBS__", json.dumps(jobs_js))
          .replace("__STAGES__", json.dumps(STAGES))
          .replace("__BOARD_STAGES__", json.dumps(BOARD_STAGES))
          .replace("__CLOSED_STAGES__", json.dumps(CLOSED_STAGES))
          .replace("__FACET_DEFS__", json.dumps(FACETS))
          .replace("__FACET_META__", json.dumps(facet_meta(jobs)))
          .replace("__PRIMARY_FACETS__", json.dumps(PRIMARY_FACETS))
          .replace("__STALE_BUCKETS__", json.dumps(list(STALE_BUCKETS)))
          .replace("__APPS__", json.dumps(apps)))

    ghosts = sum(1 for j in jobs if j["_ghost"])
    page = (PAGE
            .replace("__CSS__", CSS)
            .replace("__FILTERS__", build_filters())
            .replace("__SCORETIP__", esc(SCORE_TIP))
            .replace("__MERGED__", str(merged))
            .replace("__ROWS__", "\n".join(row(j) for j in jobs))
            .replace("__COLUMNS__", build_columns())
            .replace("__CLOSED__", build_closed())
            .replace("__JOBS__", str(len(jobs)))
            .replace("__COMPANIES__", str(len({j["comp"] for j in jobs})))
            .replace("__GHOSTS__", str(ghosts))
            .replace("__JS__", js)
            .replace("__DATE__", esc(data["date"])))

    out = run_dir / "index.html"
    out.write_text(page, encoding="utf-8")
    print(f"wrote {out} ({len(jobs)} roles, {merged} merged, {ghosts} possible ghosts, "
          f"{non_us} non-US hidden)")
    if do_open:
        webbrowser.open(out.resolve().as_uri())
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--no-open"]
    date = args[0] if args else None
    raise SystemExit(build(date, do_open="--no-open" not in sys.argv))
