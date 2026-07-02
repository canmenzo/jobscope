"""Fetch job postings from public ATS JSON APIs.

Sources (all free, public, no API key):
  greenhouse, lever, ashby, smartrecruiters, recruitee

Legal, official endpoints only. No scraping of LinkedIn/Indeed. Each company is
fetched in its own try/except so one bad endpoint never kills the run.

fetch_all() returns (jobs, statuses):
  jobs     - flat list of normalized job dicts
  statuses - per-company {name, source, slug, ok, count, error, careers_url}
             so the dashboard can show searched-vs-failed and link failures out.
"""
import datetime as dt
import html
import re
import time
from concurrent.futures import ThreadPoolExecutor

import requests

GREENHOUSE = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
LEVER = "https://api.lever.co/v0/postings/{slug}?mode=json"
ASHBY = "https://api.ashbyhq.com/posting-api/job-board/{slug}"
SMARTRECRUITERS = "https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100&offset={offset}"
RECRUITEE = "https://{slug}.recruitee.com/api/offers/"

# Public board URL per source — used as the careers link when a slug fails.
BOARD_URL = {
    "greenhouse": "https://job-boards.greenhouse.io/{slug}",
    "lever": "https://jobs.lever.co/{slug}",
    "ashby": "https://jobs.ashbyhq.com/{slug}",
    "smartrecruiters": "https://jobs.smartrecruiters.com/{slug}",
    "recruitee": "https://{slug}.recruitee.com/",
}

HEADERS = {"User-Agent": "job-hunt-skill/2.0 (personal job search)"}
TIMEOUT = 20
SLEEP_BETWEEN = 0.5  # be polite (within one company's paginated fetch)
MAX_WORKERS = 10     # parallel across companies — each hits a different board

# Pretty display names where title-casing the slug isn't enough.
NAME_OVERRIDES = {
    "abnormalsecurity": "Abnormal Security",
    "recordedfuture": "Recorded Future",
    "snowflakecomputing": "Snowflake",
    "crowdstrike": "CrowdStrike",
    "workos": "WorkOS",
    "gitlab": "GitLab",
    "hashicorp": "HashiCorp",
    "datadog": "Datadog",
    "openai": "OpenAI",
    "cockroachlabs": "Cockroach Labs",
    "dbtlabs": "dbt Labs",
    "scaleai": "Scale AI",
    "sumologic": "Sumo Logic",
    "newrelic": "New Relic",
    "mongodb": "MongoDB",
    "perplexityai": "Perplexity AI",
    "huggingface": "Hugging Face",
    "anysphere": "Anysphere (Cursor)",
    "sailpointtechnologies": "SailPoint",
    "sentinellabs": "SentinelOne",
    "wizinc": "Wiz",
    "pantherlabs": "Panther Labs",
    "materialsecurity": "Material Security",
    "orcasecurity": "Orca Security",
    "obsidiansecurity": "Obsidian Security",
    "bishopfox": "Bishop Fox",
    "hackerone": "HackerOne",
    "knowbe4": "KnowBe4",
    "1password": "1Password",
    "servicenow": "ServiceNow",
}

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")
_NL_RE = re.compile(r"\n{3,}")


def _strip_html(raw):
    if not raw:
        return ""
    text = html.unescape(raw)
    text = re.sub(r"<\s*br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</\s*(p|div|li|h[1-6])\s*>", "\n", text, flags=re.I)
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    text = _WS_RE.sub(" ", text)
    text = _NL_RE.sub("\n\n", text)
    return text.strip()


def _iso_date(val):
    """Normalize an ISO datetime string or epoch-ms to YYYY-MM-DD ('' if unknown)."""
    if not val:
        return ""
    if isinstance(val, (int, float)):
        try:
            return dt.datetime.fromtimestamp(val / 1000, dt.timezone.utc).date().isoformat()
        except (OverflowError, OSError, ValueError):
            return ""
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(val))
    return m.group(1) if m else ""


def _display(slug):
    return NAME_OVERRIDES.get(slug.lower(),
                              slug.replace("-", " ").replace("_", " ").title())


def board_url(source, slug):
    return BOARD_URL.get(source, "").format(slug=slug)


def _get(url):
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def fetch_greenhouse(slug):
    data = _get(GREENHOUSE.format(slug=slug))
    jobs = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        jobs.append({
            "id": f"greenhouse:{slug}:{j.get('id')}",
            "source": "greenhouse", "company": _display(slug), "slug": slug,
            "title": (j.get("title") or "").strip(), "location": loc,
            "country": "", "url": j.get("absolute_url", ""),
            "description": _strip_html(j.get("content", "")), "comp": "",
            "posted": _iso_date(j.get("first_published") or j.get("updated_at")),
        })
    return jobs


def fetch_lever(slug):
    data = _get(LEVER.format(slug=slug))
    jobs = []
    for j in data:
        cats = j.get("categories") or {}
        desc = j.get("descriptionPlain") or _strip_html(j.get("description", ""))
        jobs.append({
            "id": f"lever:{slug}:{j.get('id')}",
            "source": "lever", "company": _display(slug), "slug": slug,
            "title": (j.get("text") or "").strip(),
            "location": cats.get("location", "") or "", "country": "",
            "url": j.get("hostedUrl") or j.get("applyUrl", ""),
            "description": desc, "comp": cats.get("commitment", "") or "",
            "posted": _iso_date(j.get("createdAt")),
        })
    return jobs


def fetch_ashby(slug):
    data = _get(ASHBY.format(slug=slug))
    jobs = []
    for j in data.get("jobs", []):
        loc = j.get("location", "") or ""
        if j.get("isRemote") and "remote" not in loc.lower():
            loc = (loc + " (Remote)").strip()
        desc = j.get("descriptionPlain") or _strip_html(j.get("descriptionHtml", ""))
        jobs.append({
            "id": f"ashby:{slug}:{j.get('id') or j.get('jobUrl')}",
            "source": "ashby", "company": _display(slug), "slug": slug,
            "title": (j.get("title") or "").strip(), "location": loc,
            "country": "", "url": j.get("jobUrl") or j.get("applyUrl", ""),
            "description": desc, "comp": j.get("employmentType", "") or "",
            "posted": _iso_date(j.get("publishedAt") or j.get("publishedDate")),
        })
    return jobs


def fetch_smartrecruiters(slug):
    jobs, offset = [], 0
    while offset <= 200:  # cap at ~3 pages to stay polite
        data = _get(SMARTRECRUITERS.format(slug=slug, offset=offset))
        content = data.get("content", [])
        for j in content:
            loc = j.get("location", {}) or {}
            parts = [loc.get("city"), loc.get("region"), loc.get("country")]
            loc_str = ", ".join(p for p in parts if p)
            if loc.get("remote"):
                loc_str = (loc_str + " (Remote)").strip()
            jid = j.get("id") or j.get("uuid")
            jobs.append({
                "id": f"smartrecruiters:{slug}:{jid}",
                "source": "smartrecruiters", "company": _display(slug), "slug": slug,
                "title": (j.get("name") or "").strip(), "location": loc_str,
                "country": (loc.get("country") or "").upper(),
                "url": f"https://jobs.smartrecruiters.com/{slug}/{jid}",
                "description": "", "comp": "",
                "posted": _iso_date(j.get("releasedDate")),
            })
        total = data.get("totalFound", len(content))
        offset += 100
        if offset >= total or not content:
            break
        time.sleep(SLEEP_BETWEEN)
    return jobs


def fetch_recruitee(slug):
    data = _get(RECRUITEE.format(slug=slug))
    jobs = []
    for j in data.get("offers", []):
        loc = j.get("location") or ", ".join(
            p for p in [j.get("city"), j.get("country")] if p)
        jobs.append({
            "id": f"recruitee:{slug}:{j.get('id')}",
            "source": "recruitee", "company": _display(slug), "slug": slug,
            "title": (j.get("title") or "").strip(), "location": loc or "",
            "country": (j.get("country_code") or "").upper(),
            "url": j.get("careers_url") or j.get("careers_apply_url", ""),
            "description": _strip_html(j.get("description", "")), "comp": "",
            "posted": _iso_date(j.get("created_at")),
        })
    return jobs


_FETCHERS = {
    "greenhouse": fetch_greenhouse, "lever": fetch_lever, "ashby": fetch_ashby,
    "smartrecruiters": fetch_smartrecruiters, "recruitee": fetch_recruitee,
}


def _fetch_one(c):
    """Fetch one company. Returns (status, jobs, logline). Never raises."""
    source, slug = c["source"], c["slug"]
    st = {"name": _display(slug), "source": source, "slug": slug, "ok": False,
          "count": 0, "error": "", "careers_url": board_url(source, slug)}
    fetcher = _FETCHERS.get(source)
    if not fetcher:
        st["error"] = f"unknown source '{source}'"
        return st, [], f"  ! {source:15} {slug:24} -> unknown source"
    try:
        jobs = fetcher(slug)
        st["ok"] = True
        st["count"] = len(jobs)
        return st, jobs, f"  {source:15} {slug:24} -> {len(jobs)} postings"
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else "?"
        st["error"] = f"HTTP {code} (bad slug or board closed)"
        return st, [], f"  ! {source:15} {slug:24} -> HTTP {code} — skipped"
    except Exception as e:  # noqa: BLE001 — resilience: never crash the run
        st["error"] = f"{type(e).__name__}: {e}"
        return st, [], f"  ! {source:15} {slug:24} -> {type(e).__name__} — skipped"


def fetch_all(companies, log):
    """companies: list of {source, slug}.  Returns (jobs, statuses).

    Companies are fetched in parallel (each worker hits a different board, so
    no single host sees a burst); results are logged in catalog order.
    """
    out, statuses = [], []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        for st, jobs, line in ex.map(_fetch_one, companies):
            statuses.append(st)
            out.extend(jobs)
            log(line)
    return out, statuses
