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


@pytest.mark.parametrize("loc,expect_us", [
    ("Remote - MX", False),
    ("Remote - BR", False),
    ("Dublin, IE", False),
    # codes that are US states first: these must stay US.
    ("Remote - CA", True),
    ("Remote - IN", True),
    ("Remote - DE", True),
    ("Remote - PA", True),
])
def test_bare_country_code_is_not_unspecified(loc, expect_us):
    is_us, _, _ = classify_location(loc, "")
    assert is_us is expect_us


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


@pytest.mark.parametrize("loc", [
    "New York City (Remote)",
    "Remote - California",
    "Remote - CA",
    "San Francisco, CA (Remote)",
    "US, CO, Remote",
    "Remote-Friendly (Travel-Required) | San Francisco, CA | New York City, NY",
])
def test_state_tied_remote_is_its_own_type(loc):
    _, loc_type, states = classify_location(loc, "US")
    assert loc_type == "remote_state"
    assert states


@pytest.mark.parametrize("loc", [
    "Remote (USA)",
    "United States - Remote",
    "New York, New York; Miami, Florida; Remote (USA)",
    "Remote - Anywhere",
])
def test_nationwide_remote_stays_remote(loc):
    _, loc_type, _ = classify_location(loc, "US")
    assert loc_type == "remote"


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


@pytest.mark.parametrize("country,expect", [
    ("United States of America", True),   # Workday's spelling
    ("UNITED STATES", True),
    ("US", True),
    ("USA", True),
    ("Canada", False),
    ("DE", False),                        # explicit short code that isn't US
])
def test_country_field_recognition(country, expect):
    is_us, _, _ = classify_location("Greensboro, NC", country)
    assert is_us is expect


def test_unrecognised_country_defers_to_the_location_text():
    # Asserting "not US" from a country string we cannot read is how every US
    # Workday posting got dropped; an unknown name must fall through instead.
    is_us, _, states = classify_location("Charlotte, NC", "Freedonia")
    assert is_us is True and states == ["NC"]


def test_unrecognised_country_with_foreign_city_is_still_non_us():
    is_us, _, _ = classify_location("Berlin", "Freedonia")
    assert is_us is False
