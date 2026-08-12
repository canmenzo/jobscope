"""Reachability scoring.

These lock in ORDERINGS rather than exact numbers. The weights are a judgement
call and will get tuned; what must never break is the ranking — a role you can
get has to outscore one you cannot, for the reason a human would give.
"""
import pytest
from fit import MIN_SKILL_TEXT, band, blend, build_skill_idf, load_profile, score_fit

PROFILE = load_profile({
    "years_experience": 2.5,
    "target_levels": ["associate", "mid", "senior"],
    "skills": ["kql", "splunk", "sentinel", "crowdstrike", "sigma",
               "incident response", "mitre att&ck", "python", "edr"],
    "certifications": ["security+", "cysa+"],
    "salary_target": 120000,
})


def job(**kw):
    base = {"title": "Security Analyst", "description": "", "level": "",
            "yoe": None, "salary_low": 0}
    base.update(kw)
    return base


def fit(**kw):
    return score_fit(job(**kw), PROFILE)[0]


def reasons(**kw):
    return score_fit(job(**kw), PROFILE)[1]


def prose(text):
    """Pad a snippet past MIN_SKILL_TEXT so the skills component will read it.

    Anything shorter is treated as a source that didn't give us the posting,
    not as a posting that fails to mention your tools — see MIN_SKILL_TEXT.
    """
    filler = " the team collaborates closely with partners across the business."
    return text + filler * (1 + MIN_SKILL_TEXT // len(filler))


# --- years ----------------------------------------------------------------

def test_years_at_or_under_yours_is_not_penalised():
    assert fit(yoe=2) == fit(yoe=1) == fit(yoe=None if False else 2)


def test_more_years_demanded_scores_strictly_lower():
    scores = [fit(yoe=y) for y in (2, 3, 4, 6, 10)]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] > scores[-1]


def test_a_big_gap_is_called_out_in_the_reasons():
    assert any("8+ yrs" in r and "2.5" in r for r in reasons(yoe=8))


def test_unstated_years_lands_between_a_match_and_a_stretch():
    assert fit(yoe=8) < fit(yoe=None) < fit(yoe=2)


# --- seniority ------------------------------------------------------------

def test_a_targeted_level_is_not_penalised():
    # yoe is pinned, because an unstated one is inferred FROM the level and
    # would otherwise make "senior" look worse than "associate" on years.
    assert fit(level="senior", yoe=2) == fit(level="mid", yoe=2) \
        == fit(level="associate", yoe=2)


def test_levels_above_your_target_score_progressively_lower():
    scores = [fit(level=lv) for lv in ("senior", "lead", "staff", "director")]
    assert scores == sorted(scores, reverse=True)


def test_a_level_below_your_target_is_barely_penalised():
    # An entry-level posting is beneath you, not out of reach.
    assert fit(level="junior", yoe=2) > fit(level="staff", yoe=2)
    assert fit(level="junior", yoe=2) >= fit(level="senior", yoe=2) * 0.9


def test_an_internship_is_not_a_near_match():
    # Three rungs below target is a different job, not a safety school.
    assert fit(level="intern", yoe=0) < fit(level="junior", yoe=0)
    assert any("well below" in r for r in reasons(level="intern", yoe=0))


def test_unlevelled_title_is_treated_as_mid():
    assert fit(level="", yoe=2) == fit(level="mid", yoe=2)


def test_seniority_shows_up_in_the_reasons():
    assert any("staff" in r for r in reasons(level="staff"))


# --- skills ---------------------------------------------------------------

def test_more_of_your_toolkit_named_scores_higher():
    none_ = fit(description=prose("we use terraform and kubernetes"))
    some = fit(description=prose("you will write kql and tune splunk"))
    many = fit(description=prose("kql splunk sentinel crowdstrike sigma python "
                                 "edr incident response mitre att&ck"))
    assert none_ < some < many


def test_no_overlap_is_flagged():
    assert any("tools" in r for r in reasons(description=prose("terraform kubernetes")))


def test_skill_matching_respects_word_boundaries():
    # "edr" must not be found inside "shredder".
    assert fit(description=prose("shredder")) == fit(description=prose("widgets"))


def test_skills_in_the_title_count():
    body = prose("we are hiring")
    assert fit(title="Splunk Detection Engineer", description=body) \
        > fit(title="Widget Engineer", description=body)


def test_a_truncated_description_is_unreadable_not_a_bad_match():
    """Aggregators return a teaser, not the posting.

    Scoring that as "mentions none of your tools" would systematically bury
    every job from a source whose API happens to truncate.
    """
    teaser = "Security Analyst wanted. Great team, competitive pay."
    assert len(teaser) < MIN_SKILL_TEXT
    assert not any("tools" in r for r in reasons(description=teaser))
    assert fit(description=teaser) > fit(description=prose("terraform kubernetes"))


# --- pay ------------------------------------------------------------------

def test_pay_near_your_target_is_not_penalised():
    assert fit(salary_low=130000) == fit(salary_low=100000)


def test_pay_far_above_your_target_reduces_fit():
    assert fit(salary_low=260000) < fit(salary_low=170000) < fit(salary_low=120000)


def test_a_high_floor_is_explained():
    assert any("above" in r for r in reasons(salary_low=300000))


def test_pay_is_ignored_when_no_target_is_set():
    p = load_profile({"years_experience": 2.5, "salary_target": 0})
    a = score_fit(job(salary_low=400000), p)[0]
    b = score_fit(job(salary_low=90000), p)[0]
    assert a == b


# --- whole-score behaviour ------------------------------------------------

def test_the_reachable_role_beats_the_senior_one():
    reachable = fit(title="Detection Engineer II", yoe=2, level="",
                    description="kql splunk sigma detection mitre att&ck",
                    salary_low=120000)
    stretch = fit(title="Staff Application Security Engineer", yoe=8,
                  level="staff", description="threat modelling appsec",
                  salary_low=250000)
    assert reachable > stretch
    assert band(reachable) == "SAFE" and band(stretch) == "REACH"


def test_score_is_bounded():
    p = load_profile({"years_experience": 0, "salary_target": 1,
                      "target_levels": ["entry"]})
    worst = score_fit(job(yoe=20, level="vp", salary_low=900000), p)[0]
    best = score_fit(job(yoe=1, level="entry", salary_low=1), PROFILE)[0]
    assert 0 <= worst <= 100 and 0 <= best <= 100


@pytest.mark.parametrize("value,expected", [
    (95, "SAFE"), (70, "SAFE"), (69, "TARGET"), (45, "TARGET"),
    (44, "REACH"), (0, "REACH"),
])
def test_band_thresholds(value, expected):
    assert band(value) == expected


def test_missing_profile_fields_do_not_crash():
    p = load_profile({})
    score, why = score_fit(job(yoe=5, level="staff"), p)
    assert 0 <= score <= 100
    assert isinstance(why, list)


# --- missing data must not read as good news ------------------------------
# The regression these lock down: the first version of the scorer awarded 72%
# of the experience weight and 70% of the pay weight to postings that stated
# neither, so the least informative listings floated to the top of the board.

def test_a_silent_posting_cannot_beat_a_confirmed_match():
    known = fit(yoe=2, level="mid", salary_low=120000,
                description=prose("kql splunk sigma crowdstrike incident response"))
    silent = fit(yoe=None, level="", salary_low=0, description="")
    assert silent < known


def test_a_silent_posting_lands_mid_pack_not_at_the_bottom():
    # Unknown is "no opinion", not "bad" — it must not sink below a role that
    # genuinely demands three times your experience.
    silent = fit(yoe=None, level="", salary_low=0, description="")
    bad = fit(yoe=10, level="staff", salary_low=300000,
              description=prose("terraform kubernetes"))
    assert bad < silent < 70


def test_thin_postings_are_labelled():
    assert any("readable" in r for r in reasons(yoe=None, level="", description=""))


def test_confidence_is_reported():
    j = job(yoe=2, level="mid", salary_low=120000, description=prose("kql"))
    score_fit(j, PROFILE)
    assert j["fit_confidence"] == 1.0
    thin = job(yoe=None, level="", salary_low=0, description="")
    score_fit(thin, PROFILE)
    assert thin["fit_confidence"] < 1.0


# --- years inferred from the title ----------------------------------------

def test_an_unstated_bar_falls_back_to_what_the_title_implies():
    # "Sr <anything>" saying nothing about years does not make it a 2-year job.
    assert fit(level="senior") < fit(level="mid") < fit(level="junior")
    assert any("senior title usually means" in r for r in reasons(level="senior"))


def test_a_stated_bar_always_wins_over_the_inference():
    assert fit(level="senior", yoe=2) > fit(level="senior")
    assert fit(level="junior", yoe=9) < fit(level="junior")


def test_unstated_years_lands_between_a_match_and_a_stretch_by_level():
    assert fit(level="staff") < fit(level="senior") < fit(level="mid", yoe=2)


# --- skills weighted by how rare they are ---------------------------------

def test_ubiquitous_skills_stop_counting_once_calibrated():
    """`python` in every posting is not evidence; `kql` in one of them is.

    Without calibration a generic engineering role scores as well on skills as
    a detection role, which is how a customer-facing AI job came out at 90.
    """
    corpus = [prose("python git docker") for _ in range(60)]
    corpus += [prose("python git docker kql sigma crowdstrike")]
    p = build_skill_idf(load_profile({
        "years_experience": 2.5, "target_levels": ["mid"],
        "skills": ["python", "git", "docker", "kql", "sigma", "crowdstrike"],
    }), corpus)
    assert p["idf"]["kql"] > p["idf"]["python"]

    common = score_fit(job(yoe=2, level="mid",
                           description=prose("python git docker")), p)[0]
    rare = score_fit(job(yoe=2, level="mid",
                         description=prose("kql sigma crowdstrike")), p)[0]
    assert common < rare


def test_calibration_needs_a_corpus_and_degrades_quietly():
    p = build_skill_idf(load_profile({"skills": ["kql"]}), ["kql"] * 3)
    assert p["idf"] == {} and p["skill_target"] == 0.0
    assert 0 <= score_fit(job(description=prose("kql")), p)[0] <= 100


# --- sponsorship ----------------------------------------------------------

def test_a_posting_that_rules_out_sponsorship_is_sunk():
    p = load_profile({"years_experience": 2.5, "needs_sponsorship": True})
    blocked = score_fit(job(yoe=1, level="mid", sponsorship="no"), p)
    assert blocked[0] < 20
    assert any("sponsor" in r for r in blocked[1])


def test_sponsorship_is_irrelevant_when_you_do_not_need_it():
    assert fit(sponsorship="no", yoe=2) == fit(sponsorship="", yoe=2)


# --- blend ----------------------------------------------------------------

def test_blend_is_weighted_toward_fit():
    # Same distance from each input, but fit moves the result further.
    assert blend(100, 0) < blend(0, 100)


def test_blend_is_monotonic_in_both_inputs():
    assert blend(50, 50) < blend(60, 50) < blend(60, 60)


def test_blend_stays_in_range():
    assert blend(0, 0) == 0 and blend(100, 100) == 100
