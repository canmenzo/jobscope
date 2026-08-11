"""Reachability scoring.

These lock in ORDERINGS rather than exact numbers. The weights are a judgement
call and will get tuned; what must never break is the ranking — a role you can
get has to outscore one you cannot, for the reason a human would give.
"""
import pytest
from fit import band, blend, load_profile, score_fit

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
    assert fit(level="senior") == fit(level="mid") == fit(level="associate")


def test_levels_above_your_target_score_progressively_lower():
    scores = [fit(level=lv) for lv in ("senior", "lead", "staff", "director")]
    assert scores == sorted(scores, reverse=True)


def test_a_level_below_your_target_is_barely_penalised():
    # An entry-level posting is beneath you, not out of reach.
    assert fit(level="junior") > fit(level="staff")
    assert fit(level="junior") >= fit(level="senior") * 0.9


def test_unlevelled_title_is_treated_as_mid():
    assert fit(level="") == fit(level="mid")


def test_seniority_shows_up_in_the_reasons():
    assert any("staff" in r for r in reasons(level="staff"))


# --- skills ---------------------------------------------------------------

def test_more_of_your_toolkit_named_scores_higher():
    none_ = fit(description="we use terraform and kubernetes")
    some = fit(description="you will write kql and tune splunk")
    many = fit(description="kql splunk sentinel crowdstrike sigma python edr "
                           "incident response mitre att&ck")
    assert none_ < some < many


def test_no_overlap_is_flagged():
    assert any("tools" in r for r in reasons(description="terraform kubernetes"))


def test_skill_matching_respects_word_boundaries():
    # "edr" must not be found inside "shredder".
    assert fit(description="shredder") == fit(description="")


def test_skills_in_the_title_count():
    assert fit(title="Splunk Detection Engineer") > fit(title="Widget Engineer")


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


# --- blend ----------------------------------------------------------------

def test_blend_is_weighted_toward_fit():
    # Same distance from each input, but fit moves the result further.
    assert blend(100, 0) < blend(0, 100)


def test_blend_is_monotonic_in_both_inputs():
    assert blend(50, 50) < blend(60, 50) < blend(60, 60)


def test_blend_stays_in_range():
    assert blend(0, 0) == 0 and blend(100, 100) == 100
