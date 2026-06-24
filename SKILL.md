---
name: job-hunt
description: >-
  Run the user's USA tech job search. Use when the user says "run my job hunt",
  "do my job search", "find me tech jobs", "set up my job hunt", or similar.
  Pulls live postings from public ATS APIs (Greenhouse, Lever, Ashby,
  SmartRecruiters, Recruitee), filters to USA-only tech roles in the user's
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
4. Confirm the choices back to the user in one line, then continue to Step 2.

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
Writes `runs/<DATE>/index.html` and opens it. The web app shows:
- a stats header (roles, new, companies with matches, searched, failed),
- **each company as a collapsible branch** with its roles underneath (score
  badge, Apply link, "NEW" badge, matched-keyword chips),
- a live search box and a **New only** toggle,
- companies that searched OK but matched nothing (collapsed list),
- **failed boards at the bottom** with the failure reason and a direct careers
  link, so dead slugs are easy to spot and prune.

## Step 4 — present in chat
Briefly recap: how many roles across how many companies, the top few matches,
how many boards failed. Remind the user the dashboard is open and that he reviews
and applies to everything himself.

## Notes
- **Sources:** Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee — all free,
  public, no API key. Adding a company = add its slug under the right source in
  `config/companies_catalog.yaml`.
- **USA only, tech only** — both are enforced in `filter.py`. Non-US locations
  and non-tech titles are dropped.
- A failing slug never crashes the run; it's logged and shown in the dashboard's
  failed section with a careers link.
- **No auto-apply, no resume/cover generation, ever.**
