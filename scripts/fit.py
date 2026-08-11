"""How reachable is this posting FOR THIS PERSON — the other half of the score.

`score.py` answers "is this the kind of job you asked for?" (relevance). It has
no idea who you are, so a Staff Product Security Engineer asking for 8 years
scores 95 to a second-year SOC analyst. This module answers the missing
question: "would they actually interview you?"

Fit is 0-100, built from four components and driven entirely by
`config/profile.yaml` (written during setup — see SKILL.md). With no profile
file, `fit_enabled` is False and the pipeline falls back to pure relevance, so
the tool still works for someone who hasn't onboarded.

  EXPERIENCE (40) — the posting's stated years vs yours. At or under your years
                    is full marks; each year above costs, and the cost is
                    steeper near the top because "8+ years" is a harder wall
                    than "4+ years" when you have 3.
  SENIORITY  (25) — the title's level vs the levels you are targeting. One step
                    up is a stretch, two steps up is a different job.
  SKILLS     (25) — how much of your toolkit the posting actually asks for.
                    Rewards overlap; never punishes a short posting.
  PAY BAND   (10) — a listed floor far above your target band is a strong hint
                    the role is pitched well above you, even when the title is
                    coy about it.

Every component returns (points, reason) so the UI can explain a low score
instead of just asserting it.
"""
import re

# Ladder used to compare a posting's level with the levels you target.
LADDER = ["intern", "entry", "junior", "associate", "mid", "senior", "lead",
          "staff", "principal", "manager", "director", "vp", "head"]
LADDER_POS = {name: i for i, name in enumerate(LADDER)}
# score.py reports "" for an unlevelled title; treat that as mid-band.
DEFAULT_LEVEL = "mid"

W_YEARS, W_LEVEL, W_SKILLS, W_PAY = 40, 25, 25, 10


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
    }


def _years_points(job_yoe, years):
    if not job_yoe:
        return W_YEARS * 0.72, ""          # unstated: mildly optimistic, not blind
    gap = job_yoe - years
    if gap <= 0:
        return W_YEARS, ""
    if gap <= 1:
        return W_YEARS * 0.80, f"wants {job_yoe}+ yrs (you have {years:g})"
    if gap <= 2:
        return W_YEARS * 0.55, f"wants {job_yoe}+ yrs (you have {years:g})"
    if gap <= 4:
        return W_YEARS * 0.25, f"wants {job_yoe}+ yrs (you have {years:g})"
    return 0.0, f"wants {job_yoe}+ yrs (you have {years:g})"


def _level_points(level, targets):
    lvl = (level or DEFAULT_LEVEL).lower()
    if lvl not in LADDER_POS:
        lvl = DEFAULT_LEVEL
    if lvl in targets:
        return W_LEVEL, ""
    pos = LADDER_POS[lvl]
    best = min(LADDER_POS.get(t, LADDER_POS[DEFAULT_LEVEL]) for t in targets)
    top = max(LADDER_POS.get(t, LADDER_POS[DEFAULT_LEVEL]) for t in targets)
    if pos < best:                          # more junior than you want
        return W_LEVEL * 0.85, f"{lvl} role, below your target"
    step = pos - top
    if step <= 1:
        return W_LEVEL * 0.55, f"{lvl} level, one step up"
    if step <= 2:
        return W_LEVEL * 0.25, f"{lvl} level, a stretch"
    return 0.0, f"{lvl} level, well above your target"


def _skill_points(text, skills, certs):
    if not skills:
        return W_SKILLS * 0.6, ""
    hits = [s for s in skills if _skill_re(s).search(text)]
    cert_hits = [c for c in certs if _skill_re(c).search(text)]
    # Overlap saturates: matching 6 of your tools is already a strong signal.
    frac = min(1.0, len(hits) / max(3.0, min(len(skills), 8)))
    pts = W_SKILLS * (0.25 + 0.75 * frac)
    if cert_hits:
        pts = min(W_SKILLS, pts + 2)
    if not hits:
        return pts, "none of your listed tools mentioned"
    return pts, ""


def _pay_points(salary_low, target):
    if not target or not salary_low:
        return W_PAY * 0.7, ""
    ratio = salary_low / target
    if ratio <= 1.35:
        return W_PAY, ""
    if ratio <= 1.8:
        return W_PAY * 0.5, f"pays from ${salary_low:,.0f} — likely pitched above you"
    return 0.0, f"pays from ${salary_low:,.0f} — well above your band"


def score_fit(job, profile):
    """Return (fit 0-100, [reasons]) for one scored job dict."""
    text = _norm((job.get("title") or "") + "\n" + (job.get("description") or ""))
    reasons = []
    total = 0.0
    for pts, why in (
        _years_points(job.get("yoe"), profile["years"]),
        _level_points(job.get("level"), profile["target_levels"]),
        _skill_points(text, profile["skills"], profile["certifications"]),
        _pay_points(job.get("salary_low"), profile["salary_target"]),
    ):
        total += pts
        if why:
            reasons.append(why)
    return int(round(max(0.0, min(100.0, total)))), reasons


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
