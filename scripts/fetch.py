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
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

GREENHOUSE = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
LEVER = "https://api.lever.co/v0/postings/{slug}?mode=json"
ASHBY = "https://api.ashbyhq.com/posting-api/job-board/{slug}"
SMARTRECRUITERS = "https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100&offset={offset}"
RECRUITEE = "https://{slug}.recruitee.com/api/offers/"
# Workday endpoints are built per-tenant in fetch_workday (tenant:wdN:site).

# Public board URL per source — used as the careers link when a slug fails.
BOARD_URL = {
    "greenhouse": "https://job-boards.greenhouse.io/{slug}",
    "lever": "https://jobs.lever.co/{slug}",
    "ashby": "https://jobs.ashbyhq.com/{slug}",
    "smartrecruiters": "https://jobs.smartrecruiters.com/{slug}",
    "recruitee": "https://{slug}.recruitee.com/",
}

HEADERS = {"User-Agent": "job-hunt-skill/2.0 (personal job search)"}
JSON_HEADERS = dict(HEADERS, **{"Content-Type": "application/json",
                                "Accept": "application/json"})
TIMEOUT = (5, 20)  # (connect, read) — a stalled host can't wedge the whole run
SLEEP_BETWEEN = 0.5  # be polite (within one company's paginated fetch)
MAX_WORKERS = 10     # parallel across companies — each hits a different board
RETRIES = 1          # one retry on timeout/connection error (not on HTTP errors)
RETRY_BACKOFF = 2.0
WORKDAY_PAGE = 20    # server-side cap; 50 returns HTTP 400
WORKDAY_MAX_PAGES = 8
WORKDAY_DEFAULT_TERMS = ("security",)

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
    "gdit": "GDIT",
    "capitalone": "Capital One",
    "nvidia": "NVIDIA",
    "usaa": "USAA",
    "pnc": "PNC",
    "tmobile": "T-Mobile",
    "keybank": "KeyBank",
    "vystarcu": "VyStar",
    "clickhouse": "ClickHouse",
    "grafanalabs": "Grafana Labs",
    "launchdarkly": "LaunchDarkly",
    "securityscorecard": "SecurityScorecard",
    "temporaltechnologies": "Temporal",
    "endorlabs": "Endor Labs",
    "runzero": "runZero",
    "oso": "Oso",
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
    if source == "workday":
        try:
            tenant, wd, site = _workday_parts(slug)
        except ValueError:
            return ""
        return f"https://{tenant}.{wd}.myworkdayjobs.com/{site}"
    return BOARD_URL.get(source, "").format(slug=slug)


def _get(url):
    """GET + parse JSON, retrying once on a transient network failure.

    A board that times out because the host is briefly throttling us would
    otherwise be reported as a dead slug and lose all of its postings. An
    HTTP error is NOT retried — that's a genuinely bad slug or closed board.
    """
    for attempt in range(RETRIES + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            break
        except (requests.Timeout, requests.ConnectionError):
            if attempt == RETRIES:
                raise
            time.sleep(RETRY_BACKOFF)
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


def _workday_parts(slug):
    """'tenant:wd5:Site_Name' -> (tenant, wd5, Site_Name)."""
    parts = [p.strip() for p in str(slug).split(":")]
    if len(parts) != 3:
        raise ValueError("workday slug must be 'tenant:wdN:site'")
    return parts


def fetch_workday(slug, terms=None):
    """Workday's public careers JSON (the same API the careers site itself calls).

    Two quirks drive the shape of this:
      * `limit` is capped at 20 server-side (50 returns HTTP 400), so a big
        employer needs real pagination — hence WORKDAY_MAX_PAGES per term.
      * `searchText` is a loose fuzzy match ("soc analyst" happily returns
        "Business Director, Insights and Analytics"), so it is used only to
        narrow the haul; the real filtering is still ours.

    The list endpoint carries no description, so postings come back with an
    empty one plus a `detail_url`. hydrate_descriptions() fills them in later,
    for survivors only — fetching 10k descriptions up front would be absurd.
    """
    tenant, wd, site = _workday_parts(slug)
    base = f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}"
    jobs, seen = [], set()
    for term in (terms or WORKDAY_DEFAULT_TERMS):
        for page in range(WORKDAY_MAX_PAGES):
            body = {"appliedFacets": {}, "limit": WORKDAY_PAGE,
                    "offset": page * WORKDAY_PAGE, "searchText": term}
            r = requests.post(base + "/jobs", headers=JSON_HEADERS, json=body,
                              timeout=TIMEOUT)
            r.raise_for_status()
            data = r.json()
            posts = data.get("jobPostings", []) or []
            for p in posts:
                path = p.get("externalPath") or ""
                if not path or path in seen:
                    continue
                seen.add(path)
                jobs.append({
                    "id": f"workday:{tenant}:{path.rsplit('_', 1)[-1] or path}",
                    "source": "workday", "company": _display(tenant), "slug": slug,
                    "title": (p.get("title") or "").strip(),
                    "location": p.get("locationsText", "") or "",
                    "country": "", "description": "", "comp": "", "posted": "",
                    "url": f"https://{tenant}.{wd}.myworkdayjobs.com/{site}{path}",
                    "detail_url": base + path,
                })
            if len(posts) < WORKDAY_PAGE or (page + 1) * WORKDAY_PAGE >= data.get("total", 0):
                break
            time.sleep(SLEEP_BETWEEN)
    return jobs


def hydrate_descriptions(jobs, log=None):
    """Fill in descriptions for postings whose list endpoint had none.

    Only called for jobs that already survived the title-level gate, so the
    request count tracks matches rather than the size of the employer.
    """
    todo = [j for j in jobs if j.get("detail_url") and not j.get("description")]
    if not todo:
        return jobs

    def one(j):
        try:
            info = _get(j["detail_url"]).get("jobPostingInfo", {}) or {}
            j["description"] = _strip_html(info.get("jobDescription", ""))
            j["posted"] = _iso_date(info.get("startDate"))
            j["location"] = info.get("location") or j["location"]
            j["country"] = (info.get("country") or {}).get("descriptor", "") \
                if isinstance(info.get("country"), dict) else (info.get("country") or "")
            if info.get("externalUrl"):
                j["url"] = info["externalUrl"]
        except Exception:  # noqa: BLE001 — a missing detail must not kill the run
            pass
        return j

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        list(ex.map(one, todo))
    if log:
        log(f"  hydrated {len(todo)} Workday descriptions")
    return jobs


_FETCHERS = {
    "greenhouse": fetch_greenhouse, "lever": fetch_lever, "ashby": fetch_ashby,
    "smartrecruiters": fetch_smartrecruiters, "recruitee": fetch_recruitee,
    "workday": fetch_workday,
}


def _fetch_one(c):
    """Fetch one company. Returns (status, jobs, logline). Never raises."""
    source, slug = c["source"], c["slug"]
    name = _display(slug.split(":")[0] if source == "workday" else slug)
    st = {"name": name, "source": source, "slug": slug, "ok": False,
          "count": 0, "error": "", "careers_url": board_url(source, slug)}
    fetcher = _FETCHERS.get(source)
    if not fetcher:
        st["error"] = f"unknown source '{source}'"
        return st, [], f"! {source:15} {slug:24} -> unknown source"
    try:
        jobs = fetcher(slug, c["terms"]) if source == "workday" else fetcher(slug)
        st["ok"] = True
        st["count"] = len(jobs)
        return st, jobs, f"  {source:15} {slug:24} -> {len(jobs)} postings"
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else "?"
        st["error"] = f"HTTP {code} (bad slug or board closed)"
        return st, [], f"! {source:15} {slug:24} -> HTTP {code} — skipped"
    except Exception as e:  # noqa: BLE001 — resilience: never crash the run
        st["error"] = f"{type(e).__name__}: {e}"
        return st, [], f"! {source:15} {slug:24} -> {type(e).__name__} — skipped"


def fetch_all(companies, log, search_terms=None):
    """companies: list of {source, slug}.  Returns (jobs, statuses).

    Companies are fetched in parallel (each worker hits a different board, so
    no single host sees a burst). Lines are logged as each board COMPLETES,
    not in catalog order — with ordered logging one slow board silently held
    back every line behind it and the run looked frozen. Statuses are sorted
    afterwards so the run file stays deterministic.
    """
    out, statuses = [], []
    total = len(companies)
    companies = [dict(c, terms=search_terms) for c in companies]
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = [ex.submit(_fetch_one, c) for c in companies]
        for i, fut in enumerate(as_completed(futures), 1):
            st, jobs, line = fut.result()
            statuses.append(st)
            out.extend(jobs)
            log(f"  [{i:>3}/{total}] {line}")
    statuses.sort(key=lambda s: (s["source"], s["slug"]))
    return out, statuses
