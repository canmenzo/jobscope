# 🎯 JobScope

**A job search that runs itself, inside Claude Code.**

Tell it once what you're looking for and hand it your resume. After that, say
*"run my job hunt"* — ninety seconds later a dashboard opens with fresh
openings, ranked by how good each one is **for you**, not by how well the words
match.

Postings come straight from company career pages and public job APIs. No
LinkedIn, no Indeed, no scraping, no signup.

> ⚠️ It never applies to anything for you, and it doesn't write resumes or
> cover letters. It finds the jobs and keeps them organized. Applying is yours.

![The board](docs/dashboard.png)

## 📦 1. Install

Needs [Claude Code](https://claude.com/claude-code) and
[Python 3.11+](https://www.python.org/downloads/). In Claude Code:

```
/plugin marketplace add canmenzo/jobscope
/plugin install jobscope@jobscope
```

Then, in a normal terminal:

```
pip install requests pyyaml
```

Restart Claude Code.

<details>
<summary>🔧 Manual install, without the plugin system</summary>

The folder **must** be named `job-hunt`:

```bash
git clone https://github.com/canmenzo/jobscope.git ~/.claude/skills/job-hunt
cd ~/.claude/skills/job-hunt && pip install -r requirements.txt
```

Windows PowerShell:

```powershell
git clone https://github.com/canmenzo/jobscope.git "$env:USERPROFILE\.claude\skills\job-hunt"
```
</details>

## ⚙️ 2. Set it up

> **set up my job hunt**

Claude asks you a handful of questions — answer in plain English.

<details>
<summary>💬 What it'll ask</summary>

- **What kind of tech work** — cybersecurity, software engineering, data/ML,
  devops/cloud, IT, product/design, QA. Pick as many as you want.
- **Which titles** — it suggests a list, and you can add your own.
- **Which companies** — say **all**. Useless boards are easy to hide later.
- **Your resume** — give it the file path; it pulls out your years, tools and
  certs itself.
- **Four things a resume can't tell it** — target salary, target levels, remote
  preference, and whether you need visa sponsorship.

That last group carries more weight than it looks. Skip the salary and it
cheerfully recommends you $250K principal roles. Skip the resume entirely and
it can still find jobs, but only tells you *"this matches what you asked for"*
— never *"you could actually get this one."*

Everything is saved on your own machine. Nothing is uploaded anywhere.
</details>

## 🚀 3. Run it

> **run my job hunt**

The dashboard opens in your browser. Left side is your queue, right side is a
drag-and-drop pipeline — Applied, Screening, Interview, Offer. Drag a job and
it leaves the queue, so the queue only shows what you haven't dealt with yet.
It all saves in your browser.

<details>
<summary>🧭 Getting more out of the dashboard</summary>

- **Filters** — search, freshness (30 days, on by default), stage, remote,
  category, state, plus a **More** menu for level, experience, salary and
  sponsorship.
- **Every score has a reason.** Hover the number to see what pulled it up or
  down.
- **Tags** — `NO SPONSOR` / `SPONSORS` for visa situations, `GHOST` for
  postings sitting open suspiciously long or quietly relisted under a new ID.
- **Flow tab** — where your applications actually die, and CSV export.

![The flow view](docs/pipeline.png)
</details>

<details>
<summary>🪟 Windows: run it without opening Claude Code</summary>

Run `launcher\install-shortcut.ps1` once. You get two taskbar-pinnable
shortcuts — one runs a fresh hunt, one reopens your last results.
</details>

<details>
<summary>💯 What the 0-100 score means</summary>

Two questions at once: **is this the job you asked for**, and **could you
realistically get it?**

The second half is why it wanted your resume. A Staff Product Security Engineer
role asking for eight years is a perfect title match for a second-year analyst
and a complete waste of their afternoon.

🟢 Green you clear comfortably · 🟡 amber is a stretch · 🔴 red is a reach.
Anything under 55 is hidden by default.
→ [The actual math](docs/how-it-works.md#the-score-0-100)
</details>

<details>
<summary>✏️ Changing things later</summary>

You never have to touch a config file — just say it:

| You want to… | Say this |
|---|---|
| Change titles, sectors, or resume details | *"reconfigure my job search"* |
| See more (or fewer) jobs | *"lower my job hunt min score to 45"* |
| Watch a specific company | *"add Cloudflare to my job hunt"* |
| Only show things you haven't seen | *"run my job hunt, new only"* |
| Reach smaller, regional employers | *"turn on Adzuna and USAJOBS"* |

Those last two are free API keys — [Adzuna](https://developer.adzuna.com/) and
[USAJOBS](https://developer.usajobs.gov/apirequest/). Paste them to Claude and
it wires them in.
</details>

<details>
<summary>🩹 If something goes wrong</summary>

**"It says NEEDS_SETUP."** Setup hasn't run yet — say *"set up my job hunt."*

**"No jobs came back."** Filters are too tight. Lower the minimum score or turn
off the 30-day freshness filter.

**"Some companies show as failed."** Normal — companies move their job boards
constantly. One dead board never stops a run. Open the **companies** panel to
see which, and prune them.

**"pip isn't recognized."** Python isn't on your PATH. Reinstall from
[python.org](https://www.python.org/downloads/) and tick *"Add Python to
PATH."*
</details>

---

🤓 **[How it works, for nerds](docs/how-it-works.md)** — the scoring math, the
data sources, the pipeline, and how to hack on it.

MIT licensed. Issues and PRs at
[github.com/canmenzo/jobscope](https://github.com/canmenzo/jobscope).
