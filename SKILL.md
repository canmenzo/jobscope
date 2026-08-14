---
name: job-hunt
description: >-
  Run the user's USA tech job search. Use when the user says "run my job hunt",
  "do my job search", "find me tech jobs", "set up my job hunt", or similar.
  Pulls live postings from public ATS APIs (Greenhouse, Lever, Ashby,
  SmartRecruiters, Recruitee, Workday) plus broad job-search APIs (The Muse,
  Adzuna, USAJOBS), filters to USA-only tech roles in the user's
  chosen sub-sectors/titles, scores relevance 0-100, groups them by company, and
  opens a browsable web-app dashboard. First run walks the user through setup.
  Tech sector only (cybersecurity, SWE, data/ML, devops, IT, product, QA). The
  user reviews and applies himself — never auto-apply, no resume writing.
---

# job-hunt

USA-only, tech-only job search. A Python pipeline fetches live postings from
public ATS APIs, filters/scores/groups them, and renders a browsable HTML web
app. **This skill does NOT write resumes or cover letters** — it finds and
organizes openings; the user applies himself.

## When to run
Trigger phrases: "run my job hunt", "do my job search", "find me tech jobs".
Setup phrases: "set up my job hunt", "reconfigure my job search".

## Step 0 — environment (first run only)
From the skill root (`C:\Users\mehme\.claude\skills\job-hunt`):
```
pip install -r requirements.txt
```
Python 3.11+.

## Step 1 — setup (first run, or when `config/config.yaml` is missing)
If `config/config.yaml` does not exist (or the user asks to reconfigure), run
onboarding BEFORE searching. You drive this conversationally:

1. Read `config/taxonomy.yaml` (sub-sectors → titles → keywords) and
   `config/companies_catalog.yaml` (the company list, grouped by source).
2. Use **AskUserQuestion** to collect:
   - **Sub-sectors** (multiSelect) — from `taxonomy.sub_sectors` (Cybersecurity,
     Software Engineering, Data/ML/AI, DevOps/Cloud, IT/Systems, Product/Design,
     QA/Test). Tech only.
   - **Target titles** (multiSelect) — show the titles under the chosen
     sub-sectors; tell the user they can name extra titles too (free text).
   - **Companies** — default to `all` (every catalog entry). Offer: search all,
     or restrict to a subset. Most users want `all` since failed boards are
     surfaced and prunable in the dashboard.
3. Write `config/config.yaml` (see `config/config.example.yaml` for the schema):
   `country: US`, `sub_sectors: [...]`, `titles: [...]`, `companies: all` (or an
   explicit `[{source, slug}]` list), `min_score: 40`.
4. Confirm the choices back to the user in one line.
5. **Profile (drives the fit half of the score).** Ask for the path to their
   resume, read it, and extract: total years, current/most recent title, tools
   and platforms, certifications. Then ALWAYS ask the three things a resume
   cannot tell you, because each one silently disables part of the score if
   left out:
     - **target base salary** (a range is fine; take the midpoint) — without it
       the pay component is skipped and $250K senior reqs keep scoring high;
     - **target levels** — beware vendor ladders, an MDR "Principal" at 2.5
       years is not a product company's Principal, so confirm rather than
       reading the title literally;
     - remote / hybrid / on-site preference;
     - **work authorization** — ask whether they need visa sponsorship
       (F-1/OPT, H-1B, TN). If yes, set `needs_sponsorship: true`; postings
       that state they will not sponsor are then scored as unreachable and
       tagged NO SPONSOR.
   Write
   `config/profile.yaml` (schema: `config/profile.example.yaml`). If they have
   no resume handy, collect the same fields with AskUserQuestion. Skipping this
   is allowed: without the file the score is relevance-only.
6. Continue to Step 2.

## Step 2 — run the pipeline
```
python scripts/job_hunt.py                 # full run
python scripts/job_hunt.py --limit 10      # cap companies (testing)
python scripts/job_hunt.py --pick greenhouse:stripe,ashby:workos
python scripts/job_hunt.py --new-only      # only roles unseen on prior runs
```
Flags: `--min-score N` (override config), `--limit N`, `--pick "source:slug,..."`,
`--new-only`. If config is missing the script prints `NEEDS_SETUP` and exits 2 —
go back to Step 1.

It writes `runs/<DATE>/_run.json`: companies (each with ok/failed status, a
careers URL, and its matched jobs sorted by relevance) plus run stats. No
per-role folders. Already-surfaced roles are tagged (not hidden); `seen_jobs.json`
tracks them across runs.

## Step 3 — build + open the dashboard (the main UX)
```
python scripts/build_dashboard.py
```
Writes `runs/<DATE>/index.html` and opens it. Two tabs:

**Board** — a dense sortable LIST on the left (score, role, company, location,
age, salary; NEW / GHOST / N-LOC tags; hover for open-posting and move-to-
Applied buttons) and a drag-and-drop KANBAN on the right (Applied · Screening ·
Interview · Offer) plus a closed strip (Accepted · Rejected · No response).
Dragging a row onto a column tracks it and REMOVES it from the list (the list
is the triage queue); selecting that stage in the Stage filter brings it back.
Dragging a card back to the list untracks it. Every move raises an Undo toast,
and moving backwards trims the stages you undid. Click a card for a note.

**Flow** — a conversion strip plus a full-width Sankey of how roles moved
between stages, with drop-offs branching where they happened.

Two header stats open a coverage sheet: **companies** (every board searched,
matched or not, with a careers link) and **sources** (every provider the tool
can use — the ATS boards it fetches company by company, the aggregators it
searches by role — with what each brought in, and for the ones that are off,
why: a missing free API key otherwise looks identical to a source with no jobs).
Clicking a live card filters the list to it.

Filters are one thin row above the list: search, Fresh ≤30d (ON by default),
Stage, Type, Category, and More (Level, Experience, Posted, Salary, State,
Source, Company). All dropdowns are searchable multi-selects; OR within a
group, AND across groups. Filters and the active tab persist to the URL hash
and localStorage.

## Step 4 — present in chat
Briefly recap: how many roles across how many companies, the top few matches,
how many boards failed. Remind the user the dashboard is open and that he reviews
and applies to everything himself.

## Notes
- **Board sources** (per company): Greenhouse, Lever, Ashby, SmartRecruiters,
  Recruitee, Workday — all free, public, no API key. Adding a company = add its
  slug under the right source in `config/companies_catalog.yaml`. Workday slugs
  are `tenant:wdN:site` and carry the enterprise/finance/MSSP roles the startup
  boards lack; their descriptions are hydrated after the title gate.
- **Broad sources** (per role, `broad_sources:` in config): The Muse (no key),
  Adzuna and USAJOBS (free keys). These exist because a hand-curated catalog can
  only ever contain companies somebody thought to add, which skews it toward
  famous tech brands. Broad sources search by title instead and surface regional
  banks, hospital systems, MSPs and agencies — where most reachable roles are.
  A key-based source with no key configured is skipped silently.
  **If the user says the results are all big-name / too senior, this is the
  lever** — turn on the key-based ones, then widen `broad_queries`.
  Adzuna truncates descriptions, so years/sponsorship extraction won't fire on
  it; its structured `salary_min/max` is used instead (see `stated_salary`).
- **USA only, tech only** — both are enforced in `filter.py`. Non-US locations
  and non-tech titles are dropped.
- A failing slug never crashes the run; it's logged and shown in the dashboard's
  failed section with a careers link.
- **Scoring penalties** (all config-driven, see `config/config.example.yaml`):
  `freshness` decays stale postings, `max_yoe` downranks roles demanding more
  experience than the user has, `downrank_levels` / `exclude_levels` handle
  seniority. Raise `min_score` to tighten, don't hand-filter.
- **The score is a blend** of relevance (score.py) and fit (fit.py, driven by
  `config/profile.yaml`). No profile file = relevance only. Re-run the hunt
  after editing the profile; rebuilding the dashboard alone will not rescore.
- **Fit refuses to reward missing data.** Roughly half of all postings state no
  years and no salary; an unreadable component is dropped from the denominator
  and the result is shrunk toward 50, so a posting we know nothing about lands
  mid-pack rather than near the top. An unstated years bar falls back to what
  the title implies (`fit.LEVEL_YOE`). `fit_confidence` records how much was
  readable and the dashboard dashes the score chip below 0.8.
- **Skill overlap is weighted by rarity, calibrated per run** (`build_skill_idf`).
  Raw hit counts let any engineering role max out the skills component on
  `python`/`git`/`docker`; IDF over the run's own corpus makes the distinctive
  tools carry the score. Descriptions shorter than `MIN_SKILL_TEXT` count as
  unreadable, not as a bad match — otherwise truncating APIs get punished.
- **Cross-run signals:** `seen_jobs.json` drives `open_days` (how long we've
  watched a req stay open) and `reposted` (same company+title under a new id).
  Either flags a possible ghost req. Same title at the same company across
  cities is merged into one card at render time.
- Page CSS/JS live in `scripts/dashboard_assets.py` and are inlined verbatim;
  `build_dashboard.py` only substitutes `__TOKEN__` placeholders (no `.format()`,
  so JS braces need no escaping).
- Run `pytest -q` after touching `filter.py`, `score.py`, `build_dashboard.py`,
  or the extractors.
- **No auto-apply, no resume/cover generation, ever.**
