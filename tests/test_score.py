"""Relevance scoring: title coverage, seniority, freshness decay, YOE gate."""
import datetime as dt

import pytest
from score import LEVEL_PENALTY, STALE_FULL, STALE_START, age_days, score_job

TODAY = dt.date(2026, 8, 10)


def base_scope(**kw):
    s = {"titles": ["detection engineer", "security analyst"],
         "keywords": ["soc", "detection", "security", "threat intel"],
         "downrank_levels": set(), "exclude_levels": set(),
         "today": TODAY, "freshness": False, "max_yoe": 0}
    s.update(kw)
    return s


def sc(title, desc="", scope=None, **job):
    j = {"title": title, "description": desc}
    j.update(job)
    return score_job(j, scope or base_scope())["score"]


def test_exact_title_match_scores_highest():
    assert sc("Detection Engineer") >= 90


def test_clean_match_beats_verbose_title_with_same_phrase():
    assert sc("Detection Engineer") > sc("Staff Distributed Systems Detection Engineer, Platform")


def test_keyword_in_title_is_mid_band():
    assert 55 <= sc("SOC Tier 2 Specialist") < 72


def test_description_only_match_is_weak():
    assert sc("Widget Wrangler", "we run a SOC and do detection work") == 42


def test_no_match_scores_zero():
    assert sc("Barista") == 0


def test_more_keywords_do_not_inflate_score():
    one = sc("Detection Engineer")
    many = sc("Detection Engineer", "soc security threat intel detection " * 20)
    assert one == many


# --- seniority ------------------------------------------------------------

def test_downrank_level_reduces_score():
    plain = sc("Detection Engineer")
    downed = sc("Staff Detection Engineer", scope=base_scope(downrank_levels={"staff"}))
    assert downed < plain


def test_exclude_level_zeroes_score():
    assert sc("Director of Detection", scope=base_scope(exclude_levels={"director"})) == 0


def test_level_is_surfaced_without_scoring_by_default():
    # The level is detected and exposed for the UI, but with no downrank/exclude
    # configured it costs nothing — the small gap vs. a bare title is the title
    # COVERAGE effect, far short of the 25-point LEVEL_PENALTY.
    j = score_job({"title": "Senior Detection Engineer", "description": ""}, base_scope())
    plain = score_job({"title": "Detection Engineer", "description": ""}, base_scope())
    assert j["level"] == "senior"
    assert plain["score"] - j["score"] < LEVEL_PENALTY


# --- freshness ------------------------------------------------------------

@pytest.mark.parametrize("posted,expected", [
    ("2026-08-10", 0), ("2026-08-03", 7), ("2026-07-11", 30), ("", None), ("junk", None),
])
def test_age_days(posted, expected):
    assert age_days(posted, TODAY) == expected


def test_fresh_posting_is_not_penalized():
    fresh = (TODAY - dt.timedelta(days=STALE_START)).isoformat()
    scope = base_scope(freshness=True)
    assert sc("Detection Engineer", scope=scope, posted=fresh) == \
        sc("Detection Engineer", scope=base_scope())


def test_stale_posting_is_penalized():
    old = (TODAY - dt.timedelta(days=STALE_FULL)).isoformat()
    scope = base_scope(freshness=True)
    assert sc("Detection Engineer", scope=scope, posted=old) < \
        sc("Detection Engineer", scope=scope, posted=TODAY.isoformat())


def test_freshness_decay_is_monotonic():
    scope = base_scope(freshness=True)
    scores = [sc("Detection Engineer", scope=scope,
                 posted=(TODAY - dt.timedelta(days=d)).isoformat())
              for d in (0, 30, 60, 120, 200)]
    assert scores == sorted(scores, reverse=True)


def test_freshness_can_be_disabled():
    old = (TODAY - dt.timedelta(days=300)).isoformat()
    assert sc("Detection Engineer", scope=base_scope(freshness=False), posted=old) == \
        sc("Detection Engineer", scope=base_scope(freshness=False))


def test_unknown_posted_date_is_not_penalized():
    scope = base_scope(freshness=True)
    assert sc("Detection Engineer", scope=scope, posted="") == \
        sc("Detection Engineer", scope=base_scope())


# --- years of experience --------------------------------------------------

def test_yoe_below_ceiling_is_not_penalized():
    scope = base_scope(max_yoe=6)
    assert sc("Detection Engineer", scope=scope, yoe=4) == sc("Detection Engineer")


def test_yoe_above_ceiling_is_penalized_proportionally():
    scope = base_scope(max_yoe=6)
    assert sc("Detection Engineer", scope=scope, yoe=12) < \
        sc("Detection Engineer", scope=scope, yoe=8) < \
        sc("Detection Engineer", scope=scope, yoe=6)


def test_yoe_gate_off_when_max_yoe_unset():
    assert sc("Detection Engineer", scope=base_scope(max_yoe=0), yoe=15) == \
        sc("Detection Engineer")


def test_penalties_never_push_score_below_zero():
    scope = base_scope(freshness=True, max_yoe=1, downrank_levels={"staff"})
    j = score_job({"title": "Staff Widget Wrangler", "description": "soc",
                   "posted": "2020-01-01", "yoe": 20}, scope)
    assert j["score"] == 0
