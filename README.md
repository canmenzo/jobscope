# JobScope

**A job search that runs itself, inside Claude Code.**

You tell it once what kind of tech job you want and hand it your resume. After
that, you say *"run my job hunt"* and about ninety seconds later a dashboard
opens in your browser with fresh openings — sorted by how good each one is
**for you**, not just how well the words match.

It reads job postings straight from company career pages and public job APIs.
No LinkedIn, no Indeed, no scraping, no signup, no spam.

> **It never applies to anything for you, and it does not write resumes or
> cover letters.** It finds the jobs and keeps them organized. Applying is
> yours.

![The board](docs/dashboard.png)

---

## Step 1 — Install it

You need [Claude Code](https://claude.com/claude-code) and
[Python 3.11 or newer](https://www.python.org/downloads/). Both are free.

Open Claude Code and type these two lines:

```
/plugin marketplace add canmenzo/jobscope
/plugin install jobscope@jobscope
```

Then install the two things it needs to talk to job boards. In a normal
terminal (not Claude Code):

```
pip install requests pyyaml
```

Restart Claude Code and you're done installing.

<details>
<summary>Prefer not to use the plugin system? Install it manually.</summary>

Clone it into your skills folder. The folder **must** be named `job-hunt`:

```bash
git clone https://github.com/canmenzo/jobscope.git ~/.claude/skills/job-hunt
cd ~/.claude/skills/job-hunt && pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
git clone https://github.com/canmenzo/jobscope.git "$env:USERPROFILE\.claude\skills\job-hunt"
```
</details>

---

## Step 2 — Set it up

In Claude Code, say:

> **set up my job hunt**

Claude will ask you a handful of questions. Answer them however you like —
plain English is fine:

- **What kind of tech work?** Cybersecurity, software engineering, data/ML,
  devops/cloud, IT, product/design, or QA. Pick as many as you want.
- **Which job titles?** It shows you a list based on your answer above, and you
  can type in any others you care about.
- **Which companies?** Just say **all**. It searches around 250 company boards,
  and you can hide the useless ones later from the dashboard.
- **Your resume.** Give it the file path and it reads out your years of
  experience, your tools, and your certs by itself.
- **Four things a resume can't tell it:** the salary you're aiming for, the
  levels you want (junior? senior? staff?), whether you want remote, and
  whether you need visa sponsorship.

That last group matters more than it sounds. Skip the salary and it will happily
recommend you $250K principal roles. Skip the resume entirely and it can still
find jobs, but it can only tell you *"this matches what you asked for"* — not
*"you could actually get this one."*

Your answers are saved on your own machine. Nothing is uploaded anywhere.

---

## Step 3 — Run it

Say:

> **run my job hunt**

It checks every board, throws out anything that isn't a US tech role you asked
for, scores what's left, and opens the dashboard in your browser. Takes about a
minute and a half.

**On Windows**, you can skip Claude Code entirely once you're set up. Run this
once:

```powershell
launcher\install-shortcut.ps1
```

That gives you two shortcuts you can pin to the taskbar — one runs a fresh
hunt, one just reopens your last results.

---

## Using the dashboard

The left side is your **triage queue**: everything it found, best first. The
right side is a **pipeline board** — drag a job into Applied, Screening,
Interview, or Offer as things move. Once you drag a job, it leaves the queue,
so the queue only ever shows what you haven't dealt with yet.

Everything saves in your browser. Close the tab, come back tomorrow, it's all
still there.

A few things worth knowing:

- **Filters** across the top: search, freshness (last 30 days is on by
  default), stage, remote/hybrid/onsite, category, state, plus a **More** menu
  for level, experience, salary, and sponsorship.
- **Every score has a reason.** Hover the number on any job and it tells you
  exactly what pulled it up or down.
- **Tags** flag things worth catching early: `NO SPONSOR` and `SPONSORS` for
  visa situations, and `GHOST` for postings that have sat open suspiciously
  long or were quietly relisted under a new ID.
- **The Flow tab** shows where your applications actually die — how many
  reached a screen, how many an interview — and exports the lot to CSV.

*(The screenshots here use fake data. Yours starts empty.)*

![The flow view](docs/pipeline.png)

---

## What the score means

Every job gets one number from 0 to 100 that answers two questions at once:
**is this the job you asked for**, and **could you realistically get it?**

The second half is why it wanted your resume. A Staff Product Security Engineer
role asking for eight years is a perfect title match for a second-year analyst
and a complete waste of their afternoon.

The color is the shortcut: **green** you clear comfortably, **amber** is a
stretch, **red** is a reach. Hover any score to see the reasoning. By default
it hides anything below **55**.

👉 **[How it works, for nerds](docs/how-it-works.md)** — the scoring math, the
data sources, the pipeline, and how to hack on it.

---

## Changing things later

You never have to edit a config file. Just say what you want in Claude Code:

| You want to… | Say this |
|---|---|
| Change titles, sectors, or your resume details | *"reconfigure my job search"* |
| See more (or fewer) jobs | *"lower my job hunt min score to 45"* |
| Watch a specific company | *"add Cloudflare to my job hunt"* |
| Only see things you haven't seen before | *"run my job hunt, new only"* |

### Getting more jobs

Out of the box it searches those ~250 company career pages plus The Muse, which
skews heavily toward well-known tech companies. If you want the regional bank,
the hospital system, and the 40-person shop down the road to show up too, two
free API keys open that up:

- **Adzuna** — [developer.adzuna.com](https://developer.adzuna.com/)
- **USAJOBS** (federal government) —
  [developer.usajobs.gov](https://developer.usajobs.gov/apirequest/)

Sign up, paste the keys into Claude Code, and say *"add these to my job hunt."*
It'll wire them in. Until then those sources are just skipped — and the
dashboard's **sources** panel shows you exactly which boards ran, which came
back empty, and which are waiting on a key.

---

## If something goes wrong

**"It says NEEDS_SETUP."** You haven't run setup yet. Say *"set up my job
hunt."*

**"No jobs came back."** Your filters are too tight. Lower the minimum score,
or turn off the 30-day freshness filter in the dashboard.

**"Some companies show as failed."** Normal. Companies rename and move their
job boards constantly. One dead board never stops a run — open the
**companies** panel in the dashboard to see which ones and prune them.

**"pip isn't recognized."** Python isn't installed, or isn't on your PATH.
Reinstall from [python.org](https://www.python.org/downloads/) and tick *"Add
Python to PATH"* during setup.

---

MIT licensed. Issues and pull requests welcome at
[github.com/canmenzo/jobscope](https://github.com/canmenzo/jobscope).
