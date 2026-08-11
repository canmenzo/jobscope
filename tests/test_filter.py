"""Location classification and the coarse pre-scoring gate."""
import pytest
from filter import build_scope, classify_location, filter_jobs


@pytest.mark.parametrize("loc,expect_us", [
    ("San Francisco, CA", True),
    ("Remote - USA", True),
    ("New York", True),           # full state name resolves even without a code
    ("London, UK", False),
    ("Bengaluru, India", False),
    ("Ljubljana", False),
    ("", None),
])
def test_classify_location_country(loc, expect_us):
    is_us, _, _ = classify_location(loc, "")
    assert is_us is expect_us


def test_milwaukee_is_not_the_uk():
    # 'uk' is a non-US marker but must only match on word boundaries.
    is_us, _, states = classify_location("Milwaukee, WI", "")
    assert is_us is True
    assert states == ["WI"]


def test_multi_location_with_one_us_city_counts_as_us():
    is_us, _, states = classify_location("New York, NY; London", "")
    assert is_us is True
    assert "NY" in states


@pytest.mark.parametrize("loc,expected", [
    ("Remote", "remote"),
    ("Hybrid - Austin, TX", "hybrid"),
    ("Austin, TX", "onsite"),
    ("", "unspecified"),
])
def test_classify_location_type(loc, expected):
    _, loc_type, _ = classify_location(loc, expected and "US")
    assert loc_type == expected


def test_explicit_country_field_wins_over_text():
    is_us, _, _ = classify_location("Remote", "DE")
    assert is_us is False


def test_state_name_resolves_to_abbreviation():
    _, _, states = classify_location("Portland, Oregon", "")
    assert states == ["OR"]


# --- filter_jobs ----------------------------------------------------------

TAXONOMY = {
    "sub_sectors": {"cybersecurity": {"keywords": ["soc", "detection", "security"]}},
    "nontech_drop": ["account executive", "recruiter"],
}
CONFIG = {"sub_sectors": ["cybersecurity"], "titles": ["Detection Engineer"]}


@pytest.fixture
def scope():
    return build_scope(CONFIG, TAXONOMY)


def _job(**kw):
    base = {"title": "Detection Engineer", "description": "detection work",
            "location": "Remote - USA", "country": ""}
    base.update(kw)
    return base


def test_keeps_on_target_us_role(scope):
    kept, dropped = filter_jobs([_job()], scope)
    assert len(kept) == 1 and not dropped


def test_drops_non_tech_title(scope):
    _, dropped = filter_jobs([_job(title="Account Executive, Security")], scope)
    assert "non-tech" in dropped[0][1]


def test_drops_non_us(scope):
    _, dropped = filter_jobs([_job(location="Berlin, Germany")], scope)
    assert "non-US" in dropped[0][1]


def test_drops_clearance_required(scope):
    _, dropped = filter_jobs([_job(description="Requires an active TS/SCI clearance")], scope)
    assert "clearance" in dropped[0][1]


def test_drops_off_target(scope):
    _, dropped = filter_jobs(
        [_job(title="Warehouse Associate", description="lifting boxes")], scope)
    assert "off-target" in dropped[0][1]


def test_short_keyword_needs_trailing_boundary(scope):
    # 'soc' must not match 'social'.
    _, dropped = filter_jobs(
        [_job(title="Social Media Lead", description="social posts")], scope)
    assert dropped and "off-target" in dropped[0][1]


def test_build_scope_splits_slashed_titles():
    s = build_scope(
        {"titles": ["Offensive Security Engineer / Penetration Tester"]}, TAXONOMY)
    assert "offensive security engineer" in s["titles"]
    assert "penetration tester" in s["titles"]
