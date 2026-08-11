"""Cross-run history signals and duplicate merging."""
import pytest
from build_dashboard import GHOST_OPEN_DAYS, enrich, merge_duplicates, norm_title
from job_hunt import annotate_history

TODAY = "2026-08-10"


def seen_entry(company, title, first_seen):
    return {"company": company, "title": title, "first_seen": first_seen,
            "last_seen": TODAY, "url": ""}


# --- annotate_history -----------------------------------------------------

def test_open_days_counts_from_first_seen():
    jobs = [{"id": "gh:acme:1", "company": "Acme", "title": "Security Engineer"}]
    seen = {"gh:acme:1": seen_entry("Acme", "Security Engineer", "2026-07-11")}
    annotate_history(jobs, seen, TODAY)
    assert jobs[0]["open_days"] == 30
    assert jobs[0]["first_seen"] == "2026-07-11"


def test_unseen_job_is_zero_days_open():
    jobs = [{"id": "gh:acme:9", "company": "Acme", "title": "Security Engineer"}]
    annotate_history(jobs, {}, TODAY)
    assert jobs[0]["open_days"] == 0
    assert jobs[0]["first_seen"] == TODAY


def test_relisted_role_is_flagged():
    # Same company+title previously carried a different posting id.
    jobs = [{"id": "gh:acme:2", "company": "Acme", "title": "Security Engineer"}]
    seen = {"gh:acme:1": seen_entry("Acme", "Security Engineer", "2026-05-01"),
            "gh:acme:2": seen_entry("Acme", "Security Engineer", "2026-08-01")}
    annotate_history(jobs, seen, TODAY)
    assert jobs[0]["reposted"] == 1


def test_relist_matching_ignores_case_and_punctuation():
    jobs = [{"id": "gh:acme:2", "company": "Acme", "title": "Security Engineer, Platform"}]
    seen = {"gh:acme:1": seen_entry("acme", "security engineer platform", "2026-05-01"),
            "gh:acme:2": seen_entry("Acme", "Security Engineer, Platform", "2026-08-01")}
    annotate_history(jobs, seen, TODAY)
    assert jobs[0]["reposted"] == 1


def test_different_title_is_not_a_relist():
    jobs = [{"id": "gh:acme:2", "company": "Acme", "title": "Detection Engineer"}]
    seen = {"gh:acme:1": seen_entry("Acme", "Security Engineer", "2026-05-01"),
            "gh:acme:2": seen_entry("Acme", "Detection Engineer", "2026-08-01")}
    annotate_history(jobs, seen, TODAY)
    assert jobs[0]["reposted"] == 0


def test_bad_first_seen_does_not_raise():
    jobs = [{"id": "x", "company": "A", "title": "T"}]
    annotate_history(jobs, {"x": seen_entry("A", "T", "not-a-date")}, TODAY)
    assert jobs[0]["open_days"] == 0


@pytest.mark.parametrize("raw,expected", [
    ("Security Engineer, Platform", "security engineer platform"),
    ("  Sr. Detection   Engineer  ", "sr detection engineer"),
    ("", ""),
])
def test_norm_title(raw, expected):
    assert norm_title(raw) == expected


# --- ghost flag -----------------------------------------------------------

def _job(**kw):
    base = {"id": "i", "title": "Security Engineer", "comp": "Acme", "score": 80,
            "tier": "STRONG", "location": "Austin, TX", "country": "", "url": "",
            "posted": "", "age_days": 5, "yoe": None, "open_days": 0, "reposted": 0}
    base.update(kw)
    return base


def test_long_open_req_is_flagged_as_ghost():
    j = enrich(_job(open_days=GHOST_OPEN_DAYS), "greenhouse", None)
    assert j["_ghost"] is True


def test_relisted_req_is_flagged_as_ghost():
    j = enrich(_job(reposted=2), "greenhouse", None)
    assert j["_ghost"] is True


def test_fresh_single_listing_is_not_a_ghost():
    j = enrich(_job(open_days=3), "greenhouse", None)
    assert j["_ghost"] is False


# --- merge_duplicates -----------------------------------------------------

def _enriched(title, comp, loc, score):
    return enrich(_job(title=title, comp=comp, location=loc, score=score,
                       id=f"{comp}:{title}:{loc}"), "greenhouse", None)


def test_same_role_in_many_cities_becomes_one_card():
    jobs = [_enriched("Security Engineer", "Acme", "Austin, TX", 90),
            _enriched("Security Engineer", "Acme", "New York, NY", 88),
            _enriched("Security Engineer", "Acme", "Seattle, WA", 85)]
    out, merged = merge_duplicates(jobs)
    assert len(out) == 1 and merged == 2
    assert out[0]["_dupes"] == 3
    assert set(out[0]["_states"]) == {"TX", "NY", "WA"}


def test_merge_keeps_the_highest_scoring_posting_as_primary():
    jobs = [_enriched("Security Engineer", "Acme", "Austin, TX", 70),
            _enriched("Security Engineer", "Acme", "New York, NY", 95)]
    out, _ = merge_duplicates(jobs)
    assert out[0]["score"] == 95


def test_same_title_at_different_companies_is_not_merged():
    jobs = [_enriched("Security Engineer", "Acme", "Austin, TX", 90),
            _enriched("Security Engineer", "Globex", "Austin, TX", 90)]
    out, merged = merge_duplicates(jobs)
    assert len(out) == 2 and merged == 0


def test_merged_card_inherits_a_ghost_flag_from_any_duplicate():
    a = _enriched("Security Engineer", "Acme", "Austin, TX", 90)
    b = _enriched("Security Engineer", "Acme", "New York, NY", 88)
    b["_ghost"] = True
    out, _ = merge_duplicates([a, b])
    assert out[0]["_ghost"] is True


def test_unique_roles_pass_through_untouched():
    jobs = [_enriched("Security Engineer", "Acme", "Austin, TX", 90),
            _enriched("Detection Engineer", "Acme", "Austin, TX", 80)]
    out, merged = merge_duplicates(jobs)
    assert len(out) == 2 and merged == 0
    assert "_dupes" not in out[0]
