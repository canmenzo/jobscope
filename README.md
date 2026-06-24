# job-hunt

A Claude Code skill that runs a **USA-only, tech-only** job search end to end:

1. Pulls live postings from **legal, official ATS JSON APIs** — Greenhouse,
   Lever, Ashby, SmartRecruiters, Recruitee. (No LinkedIn/Indeed scraping.)
2. Filters to USA tech roles in your chosen sub-sectors/titles (drops non-US,
   non-tech, and clearance-required roles).
3. Scores each role 0-100 for relevance to what you asked to search for.
4. Groups roles by company and renders a browsable HTML web app.

> **You review and apply to everything yourself. This skill never auto-applies,
> and it does not write resumes or cover letters.**

## Invoke it

In Claude Code, just say:

> run my job hunt

On first use (no `config/config.yaml`), Claude walks you through setup —
choosing sub-sectors, target titles, and companies — then runs the search. To
reconfigure later: **"set up my job hunt"**.

## Install

This is a [Claude Code](https://claude.com/claude-code) skill. Clone it into your
Claude skills directory — the folder **must** be named `job-hunt`:

```bash
# macOS / Linux
git clone https://github.com/canmenzo/jobscope.git ~/.claude/skills/job-hunt

# Windows (PowerShell)
git clone https://github.com/canmenzo/jobscope.git "$env:USERPROFILE\.claude\skills\job-hunt"
```

Install the two Python dependencies (Python 3.11+):

```bash
cd ~/.claude/skills/job-hunt          # Windows: %USERPROFILE%\.claude\skills\job-hunt
pip install -r requirements.txt
```

Restart Claude Code so it picks up the skill, then say **"run my job hunt"**.
First run walks you through setup; your answers are saved to `config/config.yaml`
(git-ignored, never shared).

## Setup (what onboarding asks)

- **Sub-sectors** (tech only): Cybersecurity, Software Engineering, Data/ML/AI,
  DevOps/SRE/Cloud, IT/Systems, Product/Design, QA/Test.
- **Target titles**: pick from the titles under your sub-sectors, or add your own.
- **Companies**: search all catalog companies (default) or a chosen subset.

Your answers are written to `config/config.yaml`
(see `config/config.example.yaml`). The title/keyword taxonomy lives in
`config/taxonomy.yaml`; the company list in `config/companies_catalog.yaml`.

## Run manually

```
python scripts/job_hunt.py                 # full run
python scripts/job_hunt.py --limit 10      # cap companies (test)
python scripts/job_hunt.py --pick "greenhouse:stripe,ashby:workos"
python scripts/job_hunt.py --min-score 70  # raise the relevance bar
python scripts/job_hunt.py --new-only      # only roles unseen on prior runs

python scripts/build_dashboard.py          # build + open the web app
python scripts/build_dashboard.py 2026-06-24   # a specific date
```

## The dashboard (how you review results)

Every run writes `runs/<DATE>/index.html` and opens it. It shows:

- a stats header — roles, new, companies with matches, searched OK, failed;
- **each company as a collapsible branch**, its roles underneath with a relevance
  score badge, an **Apply** link, a **NEW** badge, and matched-keyword chips;
- a live **search box** and a **New only** toggle;
- companies that searched OK but matched nothing (collapsed list);
- **failed boards at the bottom**, each with the failure reason and a direct
  **careers-page link** so dead slugs are easy to spot and prune.

## Relevance score (0-100)

- **78-100** — a selected title phrase appears in the job title (strongest).
- **55-77** — a sub-sector keyword appears in the job title.
- **38-54** — match only in the description (noisier; below the default cutoff).

Default `min_score` is **55**, so you see title matches by default. Lower it in
`config/config.yaml` to include description-only matches.

## Add or change companies

Edit `config/companies_catalog.yaml` — slugs grouped by ATS source. The slug is
the identifier in that ATS's public URL:

- Greenhouse: `job-boards.greenhouse.io/<slug>`
- Lever: `jobs.lever.co/<slug>`
- Ashby: `jobs.ashbyhq.com/<slug>`
- SmartRecruiters: `jobs.smartrecruiters.com/<slug>`
- Recruitee: `<slug>.recruitee.com`

A failing slug never crashes the run — it's listed in the dashboard's failed
section with a careers link. Companies on Workday/iCIMS/Google careers aren't
reachable by these public APIs.

## Layout

```
job-hunt/
  SKILL.md                  workflow Claude follows (setup + run)
  README.md                 this file
  requirements.txt
  config/
    config.yaml             your choices (written by setup)
    config.example.yaml     schema reference
    taxonomy.yaml           sub-sectors -> titles -> keywords
    companies_catalog.yaml  companies by ATS source
  scripts/
    fetch.py                pull the ATS APIs (+ per-company status)
    filter.py               USA + selected-sector gate
    score.py                0-100 relevance
    job_hunt.py             orchestrator (run this)
    build_dashboard.py      build + open the web app
  runs/<DATE>/_run.json     grouped results
  runs/<DATE>/index.html    the dashboard
  seen_jobs.json            new-vs-seen cache across runs
```
