"""Fetch job postings from public JSON APIs.

Two kinds of source, because they answer different halves of the problem.

BOARD SOURCES are per-company: you name the employer, you get its whole board.
  greenhouse, lever, ashby, smartrecruiters, recruitee, workable, rippling,
  workday
They give clean, complete, well-described postings — but only from companies
somebody put in the catalog, which skews heavily toward well-known tech firms.

BROAD SOURCES are per-query: you name the role, you get whoever is hiring for
it. These exist to fix that skew — the mid-market bank, the hospital system,
the 40-person MSP and the federal agency are never going to be in a hand-curated
list of tech boards, and they are where most of the actually-reachable jobs are.
  muse     — The Muse public API. No key, ~400k US postings, very broad
             employer mix. Its own category tagging is unreliable, so we pull
             wide and let filter.py do the real gating.
  adzuna   — free developer key (developer.adzuna.com). A true aggregator with
             full-text search; the closest legal equivalent to what you see on
             the big job boards. NOTE: descriptions come back truncated, so
             years/sponsorship extraction won't fire on these.
  usajobs  — free key (developer.usajobs.gov). Federal postings, full text and
             structured pay. A lot of genuinely mid-level cyber work.
Both key-based sources are skipped silently when no key is configured, so the
tool still runs for someone who hasn't signed up.

Legal, official endpoints only. No scraping of LinkedIn/Indeed. Each company or
query is fetched in its own try/except so one bad endpoint never kills the run.

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

# Broad (query-based) sources — see the module docstring.
MUSE = "https://www.themuse.com/api/public/jobs"
ADZUNA = "https://api.adzuna.com/v1/api/jobs/us/search/{page}"
USAJOBS = "https://data.usajobs.gov/api/search"

# The Muse paginates 20 at a time and refuses page > 99. Its category tagging is
# loose enough that "Software Engineering" returns supermarket shifts, so the
# page budget is spent where the hit rate is: "Computer and IT" is small enough
# to exhaust outright, the rest are sampled. (category, max_pages).
MUSE_SLICES = [("Computer and IT", 79), ("Software Engineering", 40),
               ("Data and Analytics", 20), ("Science and Engineering", 12)]
MUSE_PAGE_CAP = 99
ADZUNA_PAGES = 3        # 50 results each, per query
ADZUNA_MAX_AGE = 45     # days
USAJOBS_PAGE = 250      # server max is 500; 250 keeps responses manageable
USAJOBS_PAGES = 2

# Every source this tool can pull from: display name, kind, and where to read
# about it. kind "board" = per-company (you name the employer), "broad" = per
# query (you name the role). source_status() turns this into the on/off list the
# dashboard's source sheet renders, so a source that is off says so rather than
# silently contributing nothing.
SOURCE_INFO = {
    "greenhouse": ("Greenhouse", "board", "https://www.greenhouse.io/"),
    "lever": ("Lever", "board", "https://www.lever.co/"),
    "ashby": ("Ashby", "board", "https://www.ashbyhq.com/"),
    "smartrecruiters": ("SmartRecruiters", "board", "https://www.smartrecruiters.com/"),
    "recruitee": ("Recruitee", "board", "https://recruitee.com/"),
    "workday": ("Workday", "board", "https://www.workday.com/"),
    "muse": ("The Muse", "broad", "https://www.themuse.com/developers/api/v2"),
    "adzuna": ("Adzuna", "broad", "https://developer.adzuna.com/"),
    "usajobs": ("USAJOBS", "broad", "https://developer.usajobs.gov/apirequest/"),
}
# config keys that must be filled in before a keyed source can run
KEY_FIELDS = {"adzuna": ("adzuna_app_id", "adzuna_app_key"),
              "usajobs": ("usajobs_email", "usajobs_key")}

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


# --------------------------------------------------------- broad sources
# These return postings from employers nobody put in a catalog. Each one is a
# plain function returning a list of the same normalized job dicts the board
# fetchers produce, so everything downstream is unchanged.

def _co_slug(name):
    """Stable per-company key for an employer we discovered rather than chose."""
    return re.sub(r"[^a-z0-9]+", "-", (name or "unknown").lower()).strip("-") or "unknown"


def _muse_page(category, page):
    d = requests.get(MUSE, params={"page": page, "category": category},
                     headers=HEADERS, timeout=TIMEOUT)
    d.raise_for_status()
    data = d.json()
    jobs = []
    for j in data.get("results", []):
        co = j.get("company") or {}
        name = co.get("name") or "Unknown"
        locs = [x.get("name", "") for x in (j.get("locations") or []) if x.get("name")]
        jobs.append({
            "id": f"muse:{co.get('short_name') or _co_slug(name)}:{j.get('id')}",
            "source": "muse", "company": name, "slug": _co_slug(name),
            "title": (j.get("name") or "").strip(),
            "location": "; ".join(locs), "country": "",
            "url": (j.get("refs") or {}).get("landing_page", ""),
            "description": _strip_html(j.get("contents", "")), "comp": "",
            "posted": _iso_date(j.get("publication_date")),
        })
    return jobs, data.get("page_count", 0)


def fetch_muse(slices=None, log=None):
    """Sweep The Muse's public feed across a few categories.

    The first page of each category is fetched serially to learn its real page
    count, then the remainder go out in parallel. Pages are independent, so a
    single failure costs 20 postings rather than the category.
    """
    jobs, tasks = [], []
    for category, budget in (slices or MUSE_SLICES):
        try:
            first, pages = _muse_page(category, 1)
        except Exception as e:  # noqa: BLE001
            if log:
                log(f"  ! muse {category} -> {type(e).__name__}")
            continue
        jobs += first
        last = min(budget, pages, MUSE_PAGE_CAP)
        tasks += [(category, p) for p in range(2, last + 1)]

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(_muse_page, c, p): (c, p) for c, p in tasks}
        for fut in as_completed(futures):
            try:
                got, _ = fut.result()
                jobs += got
            except Exception:  # noqa: BLE001 — one lost page is not a failure
                pass
    if log:
        log(f"  muse            {len(tasks) + len(slices or MUSE_SLICES):>4} pages"
            f"        -> {len(jobs)} postings")
    return jobs


def _adzuna_query(what, app_id, app_key, page):
    r = requests.get(ADZUNA.format(page=page), headers=HEADERS, timeout=TIMEOUT,
                     params={"app_id": app_id, "app_key": app_key,
                             "results_per_page": 50, "what_phrase": what,
                             "max_days_old": ADZUNA_MAX_AGE, "sort_by": "date",
                             "content-type": "application/json"})
    r.raise_for_status()
    out = []
    for j in r.json().get("results", []):
        name = (j.get("company") or {}).get("display_name") or "Unknown"
        out.append({
            "id": f"adzuna::{j.get('id')}",
            "source": "adzuna", "company": name, "slug": _co_slug(name),
            "title": (j.get("title") or "").strip(),
            "location": (j.get("location") or {}).get("display_name", ""),
            "country": "US", "url": j.get("redirect_url", ""),
            # Adzuna returns a ~200-char teaser, never the full posting. fit.py
            # treats text this short as unreadable rather than as evidence of a
            # bad match — see MIN_SKILL_TEXT there.
            "description": _strip_html(j.get("description", "")), "comp": "",
            "posted": _iso_date(j.get("created")),
            "salary_min": j.get("salary_min"), "salary_max": j.get("salary_max"),
        })
    return out


def fetch_adzuna(queries, app_id, app_key, pages=ADZUNA_PAGES, log=None):
    if not (app_id and app_key):
        return []
    jobs, seen = [], set()
    tasks = [(q, p) for q in queries for p in range(1, pages + 1)]
    with ThreadPoolExecutor(max_workers=5) as ex:  # free tier is rate-limited
        futures = [ex.submit(_adzuna_query, q, app_id, app_key, p) for q, p in tasks]
        for fut in as_completed(futures):
            try:
                for j in fut.result():
                    if j["id"] not in seen:      # the same posting matches many queries
                        seen.add(j["id"])
                        jobs.append(j)
            except Exception:  # noqa: BLE001
                pass
    if log:
        log(f"  adzuna          {len(tasks):>4} queries      -> {len(jobs)} postings")
    return jobs


def _usajobs_query(keyword, email, key, page):
    r = requests.get(USAJOBS, timeout=TIMEOUT, params={
        "Keyword": keyword, "ResultsPerPage": USAJOBS_PAGE, "Page": page,
        "LocationName": "United States"},
        headers={"Host": "data.usajobs.gov", "User-Agent": email,
                 "Authorization-Key": key})
    r.raise_for_status()
    items = ((r.json().get("SearchResult") or {}).get("SearchResultItems") or [])
    out = []
    for it in items:
        d = it.get("MatchedObjectDescriptor") or {}
        ua = ((d.get("UserArea") or {}).get("Details") or {})
        desc = "\n\n".join(x for x in [ua.get("JobSummary"),
                                       d.get("QualificationSummary"),
                                       ua.get("Requirements")] if x)
        name = d.get("OrganizationName") or d.get("DepartmentName") or "US Government"
        pay = (d.get("PositionRemuneration") or [{}])[0]
        out.append({
            "id": f"usajobs::{it.get('MatchedObjectId')}",
            "source": "usajobs", "company": name, "slug": _co_slug(name),
            "title": (d.get("PositionTitle") or "").strip(),
            "location": d.get("PositionLocationDisplay", ""), "country": "US",
            "url": d.get("PositionURI", ""), "description": _strip_html(desc),
            "comp": "", "posted": _iso_date(d.get("PublicationStartDate")),
            "salary_min": _num(pay.get("MinimumRange")),
            "salary_max": _num(pay.get("MaximumRange")),
        })
    return out


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fetch_usajobs(queries, email, key, pages=USAJOBS_PAGES, log=None):
    if not (email and key):
        return []
    jobs, seen = [], set()
    tasks = [(q, p) for q in queries for p in range(1, pages + 1)]
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(_usajobs_query, q, email, key, p) for q, p in tasks]
        for fut in as_completed(futures):
            try:
                for j in fut.result():
                    if j["id"] not in seen:
                        seen.add(j["id"])
                        jobs.append(j)
            except Exception:  # noqa: BLE001
                pass
    if log:
        log(f"  usajobs         {len(tasks):>4} queries      -> {len(jobs)} postings")
    return jobs


def statuses_for(jobs):
    """Synthesize per-company statuses for employers we discovered by query.

    The dashboard's company panel and the run file are both keyed on
    (source, slug); board sources get that from the catalog, broad sources have
    to derive it from whoever turned up.
    """
    by_key = {}
    for j in jobs:
        key = (j["source"], j["slug"])
        st = by_key.setdefault(key, {
            "name": j.get("company") or j["slug"], "source": j["source"],
            "slug": j["slug"], "ok": True, "count": 0, "error": "",
            "careers_url": "",
        })
        st["count"] += 1
    return sorted(by_key.values(), key=lambda s: (s["source"], s["slug"]))


def source_status(config, companies):
    """Where this run was allowed to look, source by source.

    Returns one record per known source — including the ones that contributed
    nothing — with why it is off. A source that is off because a free API key is
    missing looks exactly like a source that found no jobs unless it says so.
    """
    enabled = config.get("broad_sources") or {}
    picked = {}
    for c in companies:
        picked[c["source"]] = picked.get(c["source"], 0) + 1
    out = []
    for key, (name, kind, url) in SOURCE_INFO.items():
        boards = picked.get(key, 0)
        missing = [f for f in KEY_FIELDS.get(key, ()) if not enabled.get(f)]
        if kind == "board":
            on = bool(boards)
            why = "" if on else "no boards on this ATS in your company selection"
        elif missing:
            # The flag being false is the symptom; the missing key is the cause,
            # and it is the one the reader can do something about.
            on, why = False, f"needs a free API key — set {' + '.join(missing)} in config"
        elif not enabled.get(key):
            on, why = False, f"off in config (broad_sources.{key})"
        else:
            on, why = True, ""
        out.append({"key": key, "name": name, "kind": kind, "url": url,
                    "on": on, "why": why, "boards": boards})
    return out


def fetch_broad(config, log):
    """Run whichever broad sources are switched on in config. Never raises."""
    enabled = (config.get("broad_sources") or {})
    queries = [str(t) for t in (config.get("broad_queries")
                                or config.get("titles") or []) if t]
    jobs = []

    if enabled.get("muse"):
        slices = MUSE_SLICES
        if isinstance(enabled.get("muse"), dict):
            slices = [(k, int(v)) for k, v in enabled["muse"].items()]
        try:
            jobs += fetch_muse(slices, log)
        except Exception as e:  # noqa: BLE001
            log(f"  ! muse -> {type(e).__name__}: {e}")

    if enabled.get("adzuna") and queries:
        try:
            jobs += fetch_adzuna(queries, enabled.get("adzuna_app_id"),
                                 enabled.get("adzuna_app_key"), log=log)
        except Exception as e:  # noqa: BLE001
            log(f"  ! adzuna -> {type(e).__name__}: {e}")

    if enabled.get("usajobs") and queries:
        try:
            jobs += fetch_usajobs(queries, enabled.get("usajobs_email"),
                                  enabled.get("usajobs_key"), log=log)
        except Exception as e:  # noqa: BLE001
            log(f"  ! usajobs -> {type(e).__name__}: {e}")

    return jobs, statuses_for(jobs)


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
