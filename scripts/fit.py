"""How reachable is this posting FOR THIS PERSON — the other half of the score.

`score.py` answers "is this the kind of job you asked for?" (relevance). It has
no idea who you are, so a Staff Product Security Engineer asking for 8 years
scores 95 to a second-year SOC analyst. This module answers the missing
question: "would they actually interview you?"

Fit is 0-100, built from four components and driven entirely by
`config/profile.yaml` (written during setup — see SKILL.md). With no profile
file, the pipeline falls back to pure relevance, so the tool still works for
someone who hasn't onboarded.

  EXPERIENCE (40) — the posting's stated years vs yours. At or under your years
                    is full marks; each year above costs, and the cost is
                    steeper near the top because "8+ years" is a harder wall
                    than "4+ years" when you have 3.
  SENIORITY  (25) — the title's level vs the levels you are targeting. One step
                    up is a stretch, two steps up is a different job.
  SKILLS     (25) — how much of your toolkit the posting actually asks for,
                    weighted by how RARE each skill is in this run's corpus.
  PAY BAND   (10) — a listed floor far above your target band is a strong hint
                    the role is pitched well above you, even when the title is
                    coy about it.

Two rules keep the number honest, and both exist because the first version of
this file was far too generous:

  MISSING DATA SCORES ZERO. Roughly half of all postings state no years bar and
  no salary. The old scorer handed out 72% of the experience weight and 70% of
  the pay weight for saying nothing, so the least informative postings floated to
  the top; a later version shrank the score toward a neutral 50 instead, which
  still quietly LIFTED a weak posting and needed a dashed chip in the UI to warn
  about it. Now what a posting does not state simply earns nothing, exactly like
  a bad answer, and the deduction is named in the reasons. A missing years bar is
  the one thing still inferred — from what the TITLE implies (`LEVEL_YOE`) —
  because "Sr <anything>" saying nothing about years does not make it a two-year
  job, and an unlevelled title is read as mid, the same assumption the seniority
  component already makes.

  COMMON SKILLS ARE NOT EVIDENCE. `python`, `git`, `docker` and `sql` appear in
  almost every engineering posting, so counting raw hits let any generic
  engineering role claim a full skills score. `build_skill_idf` measures how
  often each of your skills actually occurs across the run's postings and
  weights the rare ones (`kql`, `sigma`, `crowdstrike`) far above the ubiquitous
  ones. The normaliser is the corpus's own 85th-percentile match weight, so
  "full marks" means "in the top decile of this pool", not "mentioned Python".

Every component returns (points, weight, reason) so the UI can explain a low
score instead of just asserting it.
"""
import math
import re

# Ladder used to compare a posting's level with the levels you target.
LADDER = ["intern", "entry", "junior", "associate", "mid", "senior", "lead",
          "staff", "principal", "manager", "director", "vp", "head"]
LADDER_POS = {name: i for i, name in enumerate(LADDER)}
# score.py reports "" for an unlevelled title; treat that as mid-band.
DEFAULT_LEVEL = "mid"

# Years a title implies when the description names no bar. Used as a fallback
# prior, never to override a stated requirement.
LEVEL_YOE = {"intern": 0, "entry": 0, "junior": 1, "associate": 1, "mid": 3,
             "senior": 5, "lead": 7, "staff": 8, "principal": 10, "manager": 7,
             "director": 12, "vp": 15, "head": 15}

W_YEARS, W_LEVEL, W_SKILLS, W_PAY = 40, 25, 25, 10
# Fit awarded to a role that explicitly rules out sponsorship, when the profile
# needs it. Low enough to sink below everything reachable, not zero — the score
# floor is reserved for "we could not read this at all".
SPONSOR_BLOCKED = 5
# The four weights sum to 100, so a component's weight IS the number of points
# a posting forfeits by not stating it — "−25 for no readable description" is
# literal, not a metaphor.
TOTAL_WEIGHT = W_YEARS + W_LEVEL + W_SKILLS + W_PAY
# Percentile of the corpus's skill-match weight that counts as a full score,
# and the floor under it in typical-rarity skills (see build_skill_idf).
SKILL_PCTL = 0.85
SKILL_FLOOR_SKILLS = 2
# Below this many postings the corpus is too small to calibrate against.
IDF_MIN_DOCS = 40
# Shortest text we will read a skills verdict out of. Some sources hand back no
# description at all (SmartRecruiters) and aggregators hand back a truncated
# teaser; scoring those as "mentions none of your tools" would punish a posting
# for the shape of its API. Below this they count as unreadable instead.
MIN_SKILL_TEXT = 400


def _norm(s):
    return re.sub(r"[^a-z0-9+#. ]+", " ", (s or "").lower())


def _skill_re(skill):
    """Word-boundary matcher for one skill, tolerant of '+'/'#' in names."""
    return re.compile(r"(?<!\w)" + re.escape(skill.lower()) + r"(?!\w)")


def load_profile(raw):
    """Normalise config/profile.yaml into the shape the scorer expects."""
    raw = raw or {}
    levels = [str(x).lower() for x in (raw.get("target_levels") or []) if x]
    return {
        "years": float(raw.get("years_experience") or 0),
        "target_levels": levels or ["entry", "junior", "associate", "mid"],
        "skills": [str(s).lower() for s in (raw.get("skills") or []) if s],
        "certifications": [str(c).lower() for c in (raw.get("certifications") or []) if c],
        "salary_target": float(raw.get("salary_target") or 0),
        "stretch_ok": bool(raw.get("stretch_ok", True)),
        "needs_sponsorship": bool(raw.get("needs_sponsorship", False)),
        "idf": {}, "skill_target": 0.0,
    }


# ---------------------------------------------------------------- corpus IDF

def build_skill_idf(profile, descriptions):
    """Calibrate the skills component against the postings we actually pulled.

    Two numbers come out of one pass over the corpus and are stashed on the
    profile:

      idf[skill]    inverse document frequency — a skill in 60% of postings is
                    worth almost nothing, one in 2% is worth a lot.
      skill_target  the 85th-percentile weighted match across the corpus, i.e.
                    what a genuinely strong match looks like in THIS pool. A
                    fixed target can't work: it depends entirely on whether the
                    run is full of security roles or full of retail roles.

    With too few documents to calibrate, both stay empty and `_skill_points`
    falls back to the old count-based behaviour.
    """
    skills = profile.get("skills") or []
    docs = [_norm(d) for d in descriptions if d]
    if not skills or len(docs) < IDF_MIN_DOCS:
        profile["idf"], profile["skill_target"] = {}, 0.0
        return profile

    n = len(docs)
    matchers = {s: _skill_re(s) for s in skills}
    hits_per_doc = []
    df = dict.fromkeys(skills, 0)
    for doc in docs:
        present = [s for s, rx in matchers.items() if rx.search(doc)]
        for s in present:
            df[s] += 1
        hits_per_doc.append(present)

    # +1 smoothing keeps a skill nobody asks for from dominating outright.
    idf = {s: math.log((n + 1) / (df[s] + 1)) + 0.05 for s in skills}
    weights = sorted(sum(idf[s] for s in present) for present in hits_per_doc)
    target = weights[min(len(weights) - 1, int(len(weights) * SKILL_PCTL))]

    # Guard against a corpus so uniform that the percentile just measures the
    # baseline everyone shares — then "top decile" would mean "said Python".
    # Two typical-rarity skills is the least a full score may cost. On a real
    # mixed run this sits below the percentile and never binds.
    median_idf = sorted(idf.values())[len(idf) // 2]
    profile["idf"] = idf
    profile["skill_target"] = max(target, SKILL_FLOOR_SKILLS * median_idf)
    return profile


# ------------------------------------------------------------- components
# Each returns (points, weight, reason). weight == 0 means "we could not read
# this" — the component is dropped from the denominator rather than guessed at.

def _years_points(job_yoe, level, years):
    inferred = ""
    if not job_yoe:
        # An unlevelled title is read as mid here for the same reason it is in
        # _level_points: "Security Engineer" is a mid-band ask. Inferring is what
        # keeps a plain, well-written posting from being charged for a bar that
        # its title already implies.
        lvl = (level or DEFAULT_LEVEL).lower()
        if lvl not in LEVEL_YOE:
            lvl = DEFAULT_LEVEL
        job_yoe = LEVEL_YOE[lvl]
        inferred = f"no years stated; a {lvl} title usually means ~{job_yoe}"
    gap = job_yoe - years
    if gap <= 0:
        return W_YEARS, W_YEARS, inferred
    why = inferred or f"wants {job_yoe}+ yrs (you have {years:g})"
    if gap <= 1:
        return W_YEARS * 0.80, W_YEARS, why
    if gap <= 2:
        return W_YEARS * 0.55, W_YEARS, why
    if gap <= 4:
        return W_YEARS * 0.25, W_YEARS, why
    return 0.0, W_YEARS, why


def _level_points(level, targets):
    lvl = (level or DEFAULT_LEVEL).lower()
    if lvl not in LADDER_POS:
        lvl = DEFAULT_LEVEL
    if lvl in targets:
        return W_LEVEL, W_LEVEL, ""
    pos = LADDER_POS[lvl]
    best = min(LADDER_POS.get(t, LADDER_POS[DEFAULT_LEVEL]) for t in targets)
    top = max(LADDER_POS.get(t, LADDER_POS[DEFAULT_LEVEL]) for t in targets)
    if pos < best:
        # More junior than you want. One rung down is a fine safety school; an
        # internship when you have years behind you is a different career.
        down = best - pos
        if down <= 1:
            return W_LEVEL * 0.85, W_LEVEL, ""
        if down <= 2:
            return W_LEVEL * 0.60, W_LEVEL, f"{lvl} role, below your target"
        return W_LEVEL * 0.30, W_LEVEL, f"{lvl} role, well below your target"
    step = pos - top
    if step <= 1:
        return W_LEVEL * 0.55, W_LEVEL, f"{lvl} level, one step up"
    if step <= 2:
        return W_LEVEL * 0.25, W_LEVEL, f"{lvl} level, a stretch"
    return 0.0, W_LEVEL, f"{lvl} level, well above your target"


def _skill_points(text, profile):
    skills = profile.get("skills") or []
    if not skills or len(text.strip()) < MIN_SKILL_TEXT:
        return 0.0, 0.0, ""
    idf, target = profile.get("idf") or {}, profile.get("skill_target") or 0.0
    hits = [s for s in skills if _skill_re(s).search(text)]
    cert_hits = [c for c in (profile.get("certifications") or [])
                 if _skill_re(c).search(text)]

    if idf and target > 0:
        got = sum(idf.get(s, 0.0) for s in hits)
        frac = min(1.0, got / target)
        # No floor here: the whole point is that a posting asking for none of
        # your distinctive tools should score near zero on skills.
        pts = W_SKILLS * frac
    else:
        # Uncalibrated fallback: saturating hit count, as the original did.
        frac = min(1.0, len(hits) / max(3.0, min(len(skills), 8)))
        pts = W_SKILLS * (0.25 + 0.75 * frac)

    if cert_hits:
        pts = min(W_SKILLS, pts + 2)
    why = ""
    if pts < W_SKILLS * 0.35:
        why = ("mentions none of your specialist tools" if not hits
               else "only generic tooling overlap (" + ", ".join(hits[:3]) + ")")
    return pts, W_SKILLS, why


def _pay_points(salary_low, target):
    if not target or not salary_low:
        return 0.0, 0.0, ""
    ratio = salary_low / target
    if ratio <= 1.35:
        return W_PAY, W_PAY, ""
    if ratio <= 1.8:
        return W_PAY * 0.5, W_PAY, f"pays from ${salary_low:,.0f} — likely pitched above you"
    return 0.0, W_PAY, f"pays from ${salary_low:,.0f} — well above your band"


# ------------------------------------------------------------------ scoring

def score_fit(job, profile):
    """Return (fit 0-100, [reasons]) for one scored job dict."""
    text = _norm((job.get("title") or "") + "\n" + (job.get("description") or ""))

    if profile.get("needs_sponsorship") and job.get("sponsorship") == "no":
        return SPONSOR_BLOCKED, ["employer states it cannot sponsor visas"]

    reasons, got, unread = [], 0.0, []
    for label, full, (pts, weight, why) in (
        ("no years stated", W_YEARS,
         _years_points(job.get("yoe"), job.get("level"), profile["years"])),
        ("no level", W_LEVEL,
         _level_points(job.get("level"), profile["target_levels"])),
        ("no readable description", W_SKILLS, _skill_points(text, profile)),
        ("no pay range", W_PAY,
         _pay_points(job.get("salary_low"), profile["salary_target"])),
    ):
        got += pts
        if not weight:                      # nothing to read: scores zero, like
            unread.append((label, full))    # any other answer we cannot credit
        if why:
            reasons.append(why)

    fit = got / TOTAL_WEIGHT * 100.0
    if unread:
        reasons.append("−{:g} for what it does not state ({})".format(
            sum(w for _, w in unread), ", ".join(lab for lab, _ in unread)))
    if profile.get("needs_sponsorship") and job.get("sponsorship") == "yes":
        fit = min(100.0, fit + 4)
        reasons.append("sponsors visas")
    return int(round(max(0.0, min(100.0, fit)))), reasons


def blend(relevance, fit, weight=0.55):
    """One number the list can sort on.

    Relevance alone recommends jobs you cannot get; fit alone recommends jobs
    you do not want. `weight` is fit's share — tilted to fit, because the whole
    point of the profile is that reachability was the missing half.
    """
    return int(round(relevance * (1 - weight) + fit * weight))


def band(fit):
    """Coarse label for the UI. SAFE you clear comfortably, REACH you do not."""
    return "SAFE" if fit >= 70 else "TARGET" if fit >= 45 else "REACH"
