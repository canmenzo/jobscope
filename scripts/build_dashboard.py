"""Build a browsable HTML web app for a run and open it in the browser.

Reads runs/<DATE>/_run.json and renders:
  - a stats header (companies searched, matches, new roles, failed boards)
  - companies as collapsible branches, each with its jobs underneath (Apply links)
  - companies that searched OK but matched nothing, collapsed
  - failed boards at the BOTTOM, each with the failure reason + a careers link
  - a live search box and a "new only" toggle (vanilla JS, no deps)

Usage:
    python scripts/build_dashboard.py            # latest run
    python scripts/build_dashboard.py 2026-06-24 # a specific date
    python scripts/build_dashboard.py --no-open  # build but don't open
"""
import html
import json
import sys
import webbrowser
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
RUNS = SKILL_ROOT / "runs"

TIER_COLOR = {"STRONG": "#1f9d55", "GOOD": "#b7791f", "MAYBE": "#6b7280"}
SOURCE_LABEL = {"greenhouse": "GH", "lever": "LV", "ashby": "AB",
                "smartrecruiters": "SR", "recruitee": "RC"}


def esc(s):
    return html.escape(str(s or ""))


SENIOR_LEVELS = {"senior", "staff", "principal", "lead", "manager", "director", "vp", "head"}


def job_row(j):
    color = TIER_COLOR.get(j["tier"], "#6b7280")
    lvl = j.get("level", "")
    lvlchip = (f'<span class="chip lvl">{esc(lvl)}</span>'
               if lvl in SENIOR_LEVELS else "")
    chips = lvlchip + "".join(
        f'<span class="chip">{esc(m)}</span>' for m in j.get("matched", [])[:5])
    newbadge = '<span class="new">NEW</span>' if j.get("new") else ""
    comp = f' · {esc(j["comp"])}' if j.get("comp") else ""
    search = esc((j["title"] + " " + j.get("location", "")).lower())
    return f"""    <div class="job" data-search="{search}" data-new="{int(bool(j.get('new')))}">
      <div class="sc" style="color:{color};border-color:{color}">{j['score']}</div>
      <div class="jmain">
        <a class="jt" href="{esc(j['url'])}" target="_blank" rel="noopener">{esc(j['title'])}</a>{newbadge}
        <div class="jmeta">{esc(j.get('location') or 'location n/a')}{comp}</div>
        <div class="chips">{chips}</div>
      </div>
      <a class="apply" href="{esc(j['url'])}" target="_blank" rel="noopener">Apply &rarr;</a>
    </div>"""


def company_branch(c):
    rows = "\n".join(job_row(j) for j in c["jobs"])
    top = c["jobs"][0]["score"]
    color = TIER_COLOR.get(c["jobs"][0]["tier"], "#6b7280")
    src = SOURCE_LABEL.get(c["source"], c["source"][:2].upper())
    names = esc(c["name"].lower())
    return f"""<details class="co" data-names="{names}" data-jobs="{len(c['jobs'])}">
  <summary>
    <span class="cobadge" style="color:{color};border-color:{color}">{top}</span>
    <span class="coname">{esc(c['name'])}</span>
    <span class="src">{src}</span>
    <span class="cocount">{len(c['jobs'])} role{'s' if len(c['jobs'])!=1 else ''}</span>
    <a class="colink" href="{esc(c['careers_url'])}" target="_blank" rel="noopener">careers &nearr;</a>
  </summary>
  <div class="jobs">
{rows}
  </div>
</details>"""


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Job Hunt — {date}</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0;
          background: #0f1115; color: #e6e8ec; }}
  header {{ padding: 20px 28px 14px; border-bottom: 1px solid #23262d;
           position: sticky; top: 0; background: #0f1115cc; backdrop-filter: blur(8px); z-index: 5; }}
  h1 {{ margin: 0 0 8px; font-size: 19px; }}
  .stats {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }}
  .stat {{ background: #161922; border: 1px solid #23262d; border-radius: 8px;
           padding: 5px 11px; font-size: 13px; }}
  .stat b {{ font-size: 15px; }}
  .scope {{ color: #9aa0aa; font-size: 12px; margin-bottom: 12px; }}
  .tools {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
  #q {{ flex: 1; min-width: 200px; background: #161922; border: 1px solid #2c313c;
        color: #e6e8ec; border-radius: 8px; padding: 9px 12px; font-size: 14px; }}
  .tbtn {{ background: #1e222b; border: 1px solid #2c313c; color: #cfd3da;
           border-radius: 8px; padding: 8px 12px; font-size: 13px; cursor: pointer; }}
  .tbtn.on {{ background: #2563eb; color: #fff; border-color: #2563eb; }}
  .wrap {{ padding: 18px 28px 70px; max-width: 1000px; margin: 0 auto; }}
  details.co {{ background: #161922; border: 1px solid #23262d; border-radius: 12px;
                margin: 0 0 12px; overflow: hidden; }}
  summary {{ list-style: none; cursor: pointer; display: flex; align-items: center;
             gap: 12px; padding: 13px 16px; }}
  summary::-webkit-details-marker {{ display: none; }}
  summary::before {{ content: "\\25B8"; color: #6b7280; font-size: 12px; transition: transform .15s; }}
  details[open] summary::before {{ transform: rotate(90deg); }}
  .cobadge {{ border: 1px solid; border-radius: 6px; padding: 2px 8px; font-weight: 700;
              font-size: 13px; min-width: 34px; text-align: center; }}
  .coname {{ font-size: 16px; font-weight: 600; }}
  .src {{ font-size: 10px; color: #8b90a0; border: 1px solid #2c313c; border-radius: 4px;
          padding: 1px 5px; letter-spacing: .5px; }}
  .cocount {{ color: #9aa0aa; font-size: 13px; }}
  .colink {{ margin-left: auto; color: #6ea8fe; font-size: 12px; text-decoration: none; }}
  .jobs {{ border-top: 1px solid #23262d; }}
  .job {{ display: flex; align-items: center; gap: 14px; padding: 12px 16px 12px 18px;
          border-bottom: 1px solid #1c1f27; }}
  .job:last-child {{ border-bottom: none; }}
  .sc {{ border: 1px solid; border-radius: 6px; padding: 3px 0; width: 40px; text-align: center;
         font-weight: 700; font-size: 14px; flex-shrink: 0; }}
  .jmain {{ flex: 1; min-width: 0; }}
  .jt {{ color: #e6e8ec; font-size: 15px; font-weight: 600; text-decoration: none; }}
  .jt:hover {{ color: #6ea8fe; }}
  .new {{ background: #18351f; color: #51d88a; font-size: 9px; font-weight: 700;
          padding: 1px 6px; border-radius: 10px; margin-left: 8px; vertical-align: middle; }}
  .jmeta {{ color: #9aa0aa; font-size: 13px; margin-top: 2px; }}
  .chips {{ margin-top: 5px; display: flex; flex-wrap: wrap; gap: 5px; }}
  .chip {{ background: #20242e; color: #aab0bc; font-size: 10px; padding: 1px 7px; border-radius: 10px; }}
  .chip.lvl {{ background: #2a2a40; color: #bfc4ff; text-transform: capitalize; }}
  a.apply {{ background: #2563eb; color: #fff; text-decoration: none; font-size: 13px;
             font-weight: 600; padding: 8px 14px; border-radius: 8px; flex-shrink: 0; }}
  .section-h {{ color: #9aa0aa; font-size: 13px; font-weight: 600; text-transform: uppercase;
                letter-spacing: .6px; margin: 26px 0 12px; }}
  .empty-co, .failed-co {{ display: flex; align-items: center; gap: 10px; padding: 10px 14px;
            background: #14161d; border: 1px solid #23262d; border-radius: 9px; margin-bottom: 8px;
            font-size: 13px; }}
  .failed-co {{ border-color: #3a2526; }}
  .failed-co .why {{ color: #d98f8f; }}
  .failed-co .src, .empty-co .src {{ color: #8b90a0; }}
  .failed-co a, .empty-co a {{ margin-left: auto; color: #6ea8fe; text-decoration: none; font-size: 12px; }}
  .coname-sm {{ font-weight: 600; }}
  footer {{ color: #6b7280; font-size: 12px; padding: 0 28px 40px; text-align: center; }}
  .hidden {{ display: none !important; }}
</style></head>
<body>
<header>
  <h1>Job Hunt &mdash; {date} &middot; USA &middot; tech</h1>
  <div class="stats">
    <div class="stat"><b>{jobs_total}</b> roles</div>
    <div class="stat"><b>{jobs_new}</b> new</div>
    <div class="stat"><b>{companies_with_jobs}</b> companies with matches</div>
    <div class="stat"><b>{companies_ok}</b> searched ok</div>
    <div class="stat"><b>{companies_failed}</b> failed</div>
  </div>
  <div class="scope">Sectors: {sub_sectors} &nbsp;·&nbsp; Titles: {titles}</div>
  <div class="tools">
    <input id="q" placeholder="Filter roles by title, company, location…" autocomplete="off">
    <button class="tbtn" id="newBtn">New only</button>
    <button class="tbtn" id="expBtn">Expand all</button>
  </div>
</header>
<div class="wrap">
{branches}
{empty_section}
{failed_section}
</div>
<footer>Generated from runs/{date}/_run.json &middot; no applications are submitted automatically &middot; you review and apply yourself.</footer>
<script>
const q = document.getElementById('q');
const newBtn = document.getElementById('newBtn');
const expBtn = document.getElementById('expBtn');
let newOnly = false;
function apply() {{
  const term = q.value.trim().toLowerCase();
  document.querySelectorAll('details.co').forEach(co => {{
    let shown = 0;
    co.querySelectorAll('.job').forEach(job => {{
      const okText = !term || job.dataset.search.includes(term)
                     || co.dataset.names.includes(term);
      const okNew = !newOnly || job.dataset.new === '1';
      const show = okText && okNew;
      job.classList.toggle('hidden', !show);
      if (show) shown++;
    }});
    co.classList.toggle('hidden', shown === 0);
    if (term && shown > 0) co.open = true;
  }});
}}
q.addEventListener('input', apply);
newBtn.addEventListener('click', () => {{
  newOnly = !newOnly; newBtn.classList.toggle('on', newOnly); apply();
}});
expBtn.addEventListener('click', () => {{
  const cos = [...document.querySelectorAll('details.co')];
  const anyOpen = cos.some(c => c.open);
  cos.forEach(c => c.open = !anyOpen);
  expBtn.textContent = anyOpen ? 'Expand all' : 'Collapse all';
}});
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

    with_jobs = [c for c in companies if c["ok"] and c["jobs"]]
    empty = [c for c in companies if c["ok"] and not c["jobs"]]
    failed = [c for c in companies if not c["ok"]]

    branches = "\n".join(company_branch(c) for c in with_jobs) \
        or '<p style="color:#9aa0aa">No matching roles in this run. '\
           'Try lowering min_score or widening your sub-sectors/companies.</p>'

    empty_section = ""
    if empty:
        items = "\n".join(
            f'<div class="empty-co"><span class="coname-sm">{esc(c["name"])}</span>'
            f'<span class="src">{esc(SOURCE_LABEL.get(c["source"], c["source"]))}</span>'
            f'<a href="{esc(c["careers_url"])}" target="_blank" rel="noopener">careers &nearr;</a></div>'
            for c in sorted(empty, key=lambda c: c["name"].lower()))
        empty_section = (f'<div class="section-h">Searched, no matching roles '
                         f'({len(empty)})</div>\n{items}')

    failed_section = ""
    if failed:
        items = "\n".join(
            f'<div class="failed-co"><span class="coname-sm">{esc(c["name"])}</span>'
            f'<span class="src">{esc(SOURCE_LABEL.get(c["source"], c["source"]))}</span>'
            f'<span class="why">{esc(c["error"] or "could not fetch")}</span>'
            f'<a href="{esc(c["careers_url"])}" target="_blank" rel="noopener">open careers page &nearr;</a></div>'
            for c in sorted(failed, key=lambda c: c["name"].lower()))
        failed_section = (f'<div class="section-h">Could not search '
                          f'({len(failed)}) — check the careers page directly</div>\n{items}')

    page = PAGE.format(
        date=esc(data["date"]),
        jobs_total=st.get("jobs_total", 0), jobs_new=st.get("jobs_new", 0),
        companies_with_jobs=st.get("companies_with_jobs", 0),
        companies_ok=st.get("companies_ok", 0),
        companies_failed=st.get("companies_failed", 0),
        sub_sectors=esc(", ".join(data.get("sub_sectors", [])) or "—"),
        titles=esc(", ".join(data.get("titles", [])) or "—"),
        branches=branches, empty_section=empty_section, failed_section=failed_section,
    )
    out = run_dir / "index.html"
    out.write_text(page, encoding="utf-8")
    print(f"wrote {out}")
    if do_open:
        webbrowser.open(out.resolve().as_uri())
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--no-open"]
    date = args[0] if args else None
    raise SystemExit(build(date, do_open="--no-open" not in sys.argv))
