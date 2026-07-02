"""Build a browsable HTML web app for a run and open it in the browser.

Reads runs/<DATE>/_run.json and renders:
  - a stats header (roles, new, companies, non-US hidden, failed boards)
  - a FACETS bar: location type, US state, role category, seniority level, source
  - a responsive GRID of role cards (score, title, company, location, Apply)
  - a live search box + "new only" toggle (vanilla JS, no deps)
  - companies that searched OK but matched nothing, collapsed, at the bottom
  - failed boards at the very bottom with the failure reason + a careers link

Non-US roles are dropped from the grid (the search is USA-only); the count is
shown in the header so nothing silently disappears.

Usage:
    python scripts/build_dashboard.py            # latest run
    python scripts/build_dashboard.py 2026-06-24 # a specific date
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
from filter import classify_location, US_STATES  # noqa: E402

SKILL_ROOT = Path(__file__).resolve().parent.parent
RUNS = SKILL_ROOT / "runs"

TIER_COLOR = {"STRONG": "#1f9d55", "GOOD": "#b7791f", "MAYBE": "#6b7280"}
SOURCE_NAME = {"greenhouse": "Greenhouse", "lever": "Lever", "ashby": "Ashby",
               "smartrecruiters": "SmartRecruiters", "recruitee": "Recruitee"}
SENIOR_LEVELS = {"senior", "staff", "principal", "lead", "manager", "director", "vp", "head"}
LEVEL_ORDER = ["intern", "junior", "associate", "entry", "senior", "lead",
               "staff", "principal", "manager", "director", "vp", "head"]

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
AGE_LABEL = {"7d": "Last 7 days", "30d": "8–30 days", "old": "30+ days",
             "na": "Unknown"}
STALE_DAYS = 60


def esc(s):
    return html.escape(str(s or ""))


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


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
    age = None
    if j.get("posted"):
        try:
            age = (run_date - dt.date.fromisoformat(j["posted"])).days
        except ValueError:
            pass
    j["_age"] = age
    j["_agebucket"] = ("na" if age is None else
                       "7d" if age <= 7 else "30d" if age <= 30 else "old")
    if states:
        j["_region"] = ", ".join(states)
    elif loc_type in ("remote", "unspecified"):
        j["_region"] = "Remote / US"
    else:
        j["_region"] = j.get("location") or "US"
    return j


def state_tokens(j):
    # Real US states only. Remote-ness is the Type facet's job, so a stateless
    # remote role simply has no state chip (avoids the Remote vs Remote/US clash).
    return j["_states"]


def card(j):
    color = TIER_COLOR.get(j["tier"], "#6b7280")
    lvl = j.get("level", "")
    lvlchip = f'<span class="chip lvl">{esc(lvl)}</span>' if lvl in SENIOR_LEVELS else ""
    chips = lvlchip + "".join(
        f'<span class="chip">{esc(m)}</span>' for m in j.get("matched", [])[:4])
    newbadge = '<span class="new">NEW</span>' if j.get("new") else ""
    comp = j.get("comp") or ""
    type_pill = f'<span class="tpill t-{j["_type"]}">{TYPE_LABEL[j["_type"]]}</span>'
    age = j["_age"]
    if age is None:
        age_txt = ""
    elif age >= STALE_DAYS:
        age_txt = f' <span class="age stale">· {age}d ago</span>'
    else:
        age_txt = f' <span class="age">· {"today" if age <= 0 else str(age) + "d ago"}</span>'
    salary = j.get("salary") or ""
    sal_line = f'<div class="sal">{esc(salary)}</div>' if salary else ""
    search = esc((j["title"] + " " + comp + " " + j.get("location", "")).lower())
    return f"""  <div class="card" data-search="{search}" data-new="{int(bool(j.get('new')))}"
       data-type="{j['_type']}" data-level="{esc(lvl) or 'none'}" data-cat="{slug(j['_cat'])}"
       data-src="{j['_src']}" data-state="{' '.join(state_tokens(j))}"
       data-age="{j['_agebucket']}" data-sal="{int(bool(salary))}"
       data-company="{slug(comp)}" data-comp="{esc(comp.lower())}" data-score="{j['score']}">
    <div class="ctop">
      <span class="sc" style="color:{color};border-color:{color}">{j['score']}</span>
      {type_pill}{newbadge}
    </div>
    <a class="jt" href="{esc(j['url'])}" target="_blank" rel="noopener">{esc(j['title'])}</a>
    <div class="cco">{comp}</div>
    <div class="cloc">{esc(j['_region'])}{age_txt}</div>
    {sal_line}<div class="chips">{chips}</div>
    <a class="apply" href="{esc(j['url'])}" target="_blank" rel="noopener">Apply &rarr;</a>
  </div>"""


def facet_group(field, title, options):
    """options: list of (value, label, count)."""
    chips = "\n".join(
        f'    <button class="fchip" data-facet="{field}" data-val="{esc(v)}">'
        f'{esc(label)} <span class="fct">{count}</span></button>'
        for v, label, count in options if count)
    return f"""  <div class="fgroup">
    <span class="flabel">{esc(title)}</span>
{chips}
  </div>"""


def build_facets(jobs):
    def counts(keyfn):
        c = {}
        for j in jobs:
            for v in keyfn(j):
                c[v] = c.get(v, 0) + 1
        return c

    types = counts(lambda j: [j["_type"]])
    type_opts = [(t, TYPE_LABEL[t], types.get(t, 0))
                 for t in ("remote", "hybrid", "onsite", "unspecified")]

    states = counts(state_tokens)
    state_opts = sorted(((s, s, n) for s, n in states.items()),
                        key=lambda o: (-o[2], o[0]))

    cats = counts(lambda j: [j["_cat"]])
    cat_opts = sorted(((slug(c), c, n) for c, n in cats.items()),
                      key=lambda o: (-o[2], o[1]))

    levels = counts(lambda j: [j.get("level") or "none"])
    order = LEVEL_ORDER + ["none"]
    level_opts = [(lv, "Unspecified" if lv == "none" else lv.capitalize(), levels.get(lv, 0))
                  for lv in order if levels.get(lv)]

    srcs = counts(lambda j: [j["_src"]])
    src_opts = sorted(((s, SOURCE_NAME.get(s, s.title()), n) for s, n in srcs.items()),
                      key=lambda o: (-o[2], o[1]))

    ages = counts(lambda j: [j["_agebucket"]])
    age_opts = [(a, AGE_LABEL[a], ages.get(a, 0)) for a in ("7d", "30d", "old", "na")]

    sals = counts(lambda j: [str(int(bool(j.get("salary"))))])
    sal_opts = [("1", "Listed", sals.get("1", 0)), ("0", "Not listed", sals.get("0", 0))]

    return "\n".join([
        facet_group("type", "Type", type_opts),
        facet_group("cat", "Category", cat_opts),
        facet_group("level", "Level", level_opts),
        facet_group("age", "Posted", age_opts),
        facet_group("sal", "Salary", sal_opts),
        facet_group("state", "State", state_opts),
        facet_group("src", "Source", src_opts),
    ])


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Job Hunt — {date}</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0;
          background: #0f1115; color: #e6e8ec; }}
  header {{ padding: 18px 28px 12px; border-bottom: 1px solid #23262d;
           position: sticky; top: 0; background: #0f1115ee; backdrop-filter: blur(8px); z-index: 20; }}
  h1 {{ margin: 0 0 8px; font-size: 19px; }}
  .stats {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }}
  .stat {{ background: #161922; border: 1px solid #23262d; border-radius: 8px;
           padding: 5px 11px; font-size: 13px; }}
  .stat b {{ font-size: 15px; }}
  .stat.clickable {{ cursor: pointer; user-select: none; }}
  .stat.clickable:hover {{ border-color: #3a4150; }}
  .stat.clickable.open {{ background: #1d2433; border-color: #2563eb; }}
  .cpanel {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 10px;
             max-height: 30vh; overflow: auto; padding: 10px; background: #0d0f13;
             border: 1px solid #23262d; border-radius: 10px; }}
  .tools {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
  #q {{ flex: 1; min-width: 220px; background: #161922; border: 1px solid #2c313c;
        color: #e6e8ec; border-radius: 8px; padding: 9px 12px; font-size: 14px; }}
  .tbtn {{ background: #1e222b; border: 1px solid #2c313c; color: #cfd3da;
           border-radius: 8px; padding: 8px 12px; font-size: 13px; cursor: pointer; }}
  .tbtn.on {{ background: #2563eb; color: #fff; border-color: #2563eb; }}
  #shown {{ color: #9aa0aa; font-size: 13px; margin-left: 2px; }}
  .facets {{ display: flex; flex-direction: column; gap: 7px; padding: 12px 28px;
             border-bottom: 1px solid #23262d; background: #0d0f13;
             position: sticky; top: 0; z-index: 10; max-height: 38vh; overflow: auto; }}
  .fgroup {{ display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }}
  .flabel {{ color: #6b7280; font-size: 11px; text-transform: uppercase; letter-spacing: .6px;
             width: 74px; flex-shrink: 0; }}
  .fchip {{ background: #161922; border: 1px solid #2c313c; color: #cfd3da; cursor: pointer;
            border-radius: 14px; padding: 4px 10px; font-size: 12px; }}
  .fchip:hover {{ border-color: #3a4150; }}
  .fchip.on {{ background: #2563eb; color: #fff; border-color: #2563eb; }}
  .fct {{ opacity: .6; font-size: 11px; }}
  .wrap {{ padding: 18px 28px 70px; max-width: 1400px; margin: 0 auto; }}
  .grid {{ display: grid; gap: 14px; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); }}
  .card {{ background: #161922; border: 1px solid #23262d; border-radius: 12px; padding: 14px;
           display: flex; flex-direction: column; gap: 6px; }}
  .card:hover {{ border-color: #313742; }}
  .ctop {{ display: flex; align-items: center; gap: 8px; }}
  .sc {{ border: 1px solid; border-radius: 6px; padding: 2px 0; width: 40px; text-align: center;
         font-weight: 700; font-size: 14px; }}
  .tpill {{ font-size: 10px; padding: 2px 8px; border-radius: 10px; font-weight: 600; }}
  .t-remote {{ background: #14302a; color: #5bd6ac; }}
  .t-hybrid {{ background: #2c2a16; color: #e0c061; }}
  .t-onsite {{ background: #1c2333; color: #8fb3ff; }}
  .t-unspecified {{ background: #20242e; color: #9aa0aa; }}
  .jt {{ color: #e6e8ec; font-size: 15px; font-weight: 600; text-decoration: none; line-height: 1.3; }}
  .jt:hover {{ color: #6ea8fe; }}
  .new {{ background: #18351f; color: #51d88a; font-size: 9px; font-weight: 700;
          padding: 1px 6px; border-radius: 10px; }}
  .cco {{ color: #cfd3da; font-size: 13px; font-weight: 500; }}
  .cloc {{ color: #9aa0aa; font-size: 12px; }}
  .age {{ color: #8b90a0; }}
  .age.stale {{ color: #d9a15f; }}
  .sal {{ color: #7ec9a3; font-size: 12px; font-weight: 600; }}
  .chips {{ display: flex; flex-wrap: wrap; gap: 5px; margin-top: 2px; }}
  .chip {{ background: #20242e; color: #aab0bc; font-size: 10px; padding: 1px 7px; border-radius: 10px; }}
  .chip.lvl {{ background: #2a2a40; color: #bfc4ff; text-transform: capitalize; }}
  a.apply {{ background: #2563eb; color: #fff; text-decoration: none; font-size: 13px;
             font-weight: 600; padding: 8px 0; border-radius: 8px; text-align: center; margin-top: 4px; }}
  .nomatch {{ color: #9aa0aa; padding: 30px 0; text-align: center; }}
  .section-h {{ color: #9aa0aa; font-size: 13px; font-weight: 600; text-transform: uppercase;
                letter-spacing: .6px; margin: 30px 0 12px; }}
  .empty-co, .failed-co {{ display: flex; align-items: center; gap: 10px; padding: 10px 14px;
            background: #14161d; border: 1px solid #23262d; border-radius: 9px; margin-bottom: 8px;
            font-size: 13px; }}
  .failed-co {{ border-color: #3a2526; }}
  .failed-co .why {{ color: #d98f8f; }}
  .src {{ color: #8b90a0; font-size: 11px; }}
  .failed-co a, .empty-co a {{ margin-left: auto; color: #6ea8fe; text-decoration: none; font-size: 12px; }}
  .coname-sm {{ font-weight: 600; }}
  footer {{ color: #6b7280; font-size: 12px; padding: 0 28px 40px; text-align: center; }}
  .hidden {{ display: none !important; }}
</style></head>
<body>
<header>
  <h1>Job Hunt &mdash; {date} &middot; USA &middot; tech</h1>
  <div class="stats">
    <div class="stat"><b id="stRoles">{jobs_total}</b> roles</div>
    <div class="stat"><b id="stNew">{jobs_new}</b> new</div>
    <div class="stat clickable" id="companiesStat"><b id="stCompanies">{companies_with_jobs}</b> companies &#9662;</div>
    <div class="stat"><b>{non_us}</b> non-US hidden</div>
    <div class="stat"><b>{companies_failed}</b> boards failed</div>
  </div>
  <div class="cpanel hidden" id="cpanel"></div>
  <div class="tools">
    <input id="q" placeholder="Search title, company, location…" autocomplete="off">
    <select id="sortSel" class="tbtn">
      <option value="score">Sort: score</option>
      <option value="new">Sort: new first</option>
      <option value="company">Sort: company A–Z</option>
    </select>
    <button class="tbtn" id="newBtn">New only</button>
    <button class="tbtn" id="clrBtn">Clear filters</button>
    <span id="shown"></span>
  </div>
</header>
<div class="facets">
{facets}
</div>
<div class="wrap">
  <div class="grid" id="grid">
{cards}
  </div>
  <div class="nomatch hidden" id="noMatch">No roles match these filters.</div>
{empty_section}
{failed_section}
</div>
<footer>Generated from runs/{date}/_run.json &middot; no applications are submitted automatically &middot; you review and apply yourself.</footer>
<script>
const CNAMES = {cnames};
const q = document.getElementById('q');
const grid = document.getElementById('grid');
const cards = [...document.querySelectorAll('.card')];
const shown = document.getElementById('shown');
const noMatch = document.getElementById('noMatch');
const cpanel = document.getElementById('cpanel');
const companiesStat = document.getElementById('companiesStat');
const sortSel = document.getElementById('sortSel');
const stRoles = document.getElementById('stRoles');
const stNew = document.getElementById('stNew');
const stCompanies = document.getElementById('stCompanies');
const facets = {{type:new Set(), cat:new Set(), level:new Set(), state:new Set(),
                 src:new Set(), age:new Set(), sal:new Set(), company:new Set()}};
let newOnly = false;

function vals(card, f) {{
  return f === 'state' ? card.dataset.state.split(' ').filter(Boolean) : [card.dataset[f]];
}}
// Does the card pass every active filter, optionally skipping one facet group?
function passes(card, skip) {{
  const term = q.value.trim().toLowerCase();
  if (term && !card.dataset.search.includes(term)) return false;
  if (newOnly && card.dataset.new !== '1') return false;
  for (const f in facets) {{
    if (f === skip || !facets[f].size) continue;
    if (!vals(card, f).some(v => facets[f].has(v))) return false;
  }}
  return true;
}}
function buildPanel() {{
  const comps = {{}};
  cards.forEach(c => {{ if (passes(c, 'company')) comps[c.dataset.company] = (comps[c.dataset.company] || 0) + 1; }});
  const slugs = Object.keys(comps).sort((a, b) => (CNAMES[a] || a).localeCompare(CNAMES[b] || b));
  cpanel.innerHTML = slugs.map(s =>
    `<button class="fchip${{facets.company.has(s) ? ' on' : ''}}" data-facet="company" data-val="${{s}}">`
    + `${{CNAMES[s] || s}} <span class="fct">${{comps[s]}}</span></button>`).join('')
    || '<span class="src">No companies in view.</span>';
}}
function apply() {{
  let n = 0;
  cards.forEach(card => {{
    const show = passes(card, null);
    card.classList.toggle('hidden', !show);
    if (show) n++;
  }});
  buildPanel();
  const vis = cards.filter(c => !c.classList.contains('hidden'));
  stRoles.textContent = vis.length;
  stNew.textContent = vis.filter(c => c.dataset.new === '1').length;
  stCompanies.textContent = new Set(vis.map(c => c.dataset.company)).size;
  shown.textContent = n + ' / ' + cards.length + ' shown';
  noMatch.classList.toggle('hidden', n !== 0);
}}
function sortGrid() {{
  const m = sortSel.value;
  cards.slice().sort((a, b) => {{
    if (m === 'company') return a.dataset.comp.localeCompare(b.dataset.comp) || b.dataset.score - a.dataset.score;
    if (m === 'new') return (b.dataset.new - a.dataset.new) || b.dataset.score - a.dataset.score;
    return (b.dataset.score - a.dataset.score) || a.dataset.comp.localeCompare(b.dataset.comp);
  }}).forEach(c => grid.appendChild(c));
}}
q.addEventListener('input', apply);
sortSel.addEventListener('change', sortGrid);
companiesStat.addEventListener('click', () => {{
  cpanel.classList.toggle('hidden');
  companiesStat.classList.toggle('open', !cpanel.classList.contains('hidden'));
}});
document.getElementById('newBtn').addEventListener('click', e => {{
  newOnly = !newOnly; e.target.classList.toggle('on', newOnly); apply();
}});
document.querySelectorAll('.facets .fchip').forEach(chip => chip.addEventListener('click', () => {{
  const f = chip.dataset.facet, v = chip.dataset.val;
  if (facets[f].has(v)) facets[f].delete(v); else facets[f].add(v);
  chip.classList.toggle('on'); apply();
}}));
cpanel.addEventListener('click', e => {{
  const chip = e.target.closest('.fchip'); if (!chip) return;
  const v = chip.dataset.val;
  if (facets.company.has(v)) facets.company.delete(v); else facets.company.add(v);
  apply();
}});
document.getElementById('clrBtn').addEventListener('click', () => {{
  for (const f in facets) facets[f].clear();
  document.querySelectorAll('.facets .fchip.on').forEach(c => c.classList.remove('on'));
  newOnly = false; document.getElementById('newBtn').classList.remove('on');
  q.value = ''; apply();
}});
apply();
</script>
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

    jobs = []
    non_us = 0
    for c in companies:
        if not (c["ok"] and c["jobs"]):
            continue
        for j in c["jobs"]:
            j["comp"] = c["name"]  # board-level company name (per-job comp is just employment type)
            enrich(j, c["source"], run_date)
            if j["_us"] is False:
                non_us += 1
                continue
            jobs.append(j)
    jobs.sort(key=lambda j: (-j["score"], j["comp"].lower(), j["title"].lower()))

    empty = [c for c in companies if c["ok"] and not c["jobs"]]
    failed = [c for c in companies if not c["ok"]]

    cards = "\n".join(card(j) for j in jobs) or ""
    facets = build_facets(jobs) if jobs else ""
    cnames = json.dumps({slug(j["comp"]): j["comp"] for j in jobs if j.get("comp")})

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

    page = PAGE.format(
        date=esc(data["date"]),
        jobs_total=len(jobs), jobs_new=sum(1 for j in jobs if j.get("new")),
        companies_with_jobs=len({j["comp"] for j in jobs}),
        non_us=non_us, companies_failed=st.get("companies_failed", 0),
        facets=facets, cards=cards, cnames=cnames,
        empty_section=empty_section, failed_section=failed_section,
    )
    out = run_dir / "index.html"
    out.write_text(page, encoding="utf-8")
    print(f"wrote {out} ({len(jobs)} roles, {non_us} non-US hidden)")
    if do_open:
        webbrowser.open(out.resolve().as_uri())
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--no-open"]
    date = args[0] if args else None
    raise SystemExit(build(date, do_open="--no-open" not in sys.argv))
