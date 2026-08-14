"""Which providers a run was allowed to look at, and what the sheet shows."""
from build_dashboard import source_data
from fetch import SOURCE_INFO, source_status

COMPANIES = [{"source": "greenhouse", "slug": "acme"},
             {"source": "greenhouse", "slug": "beta"},
             {"source": "ashby", "slug": "gamma"}]


def status(config, companies=COMPANIES):
    return {s["key"]: s for s in source_status(config, companies)}


# --- source_status --------------------------------------------------------

def test_every_known_source_is_reported_even_when_it_never_ran():
    assert set(status({})) == set(SOURCE_INFO)


def test_board_source_is_on_when_boards_were_selected():
    s = status({})["greenhouse"]
    assert s["on"] and s["boards"] == 2 and s["why"] == ""


def test_board_source_with_no_boards_says_so():
    s = status({})["lever"]
    assert not s["on"] and "company selection" in s["why"]


def test_keyless_broad_source_follows_its_flag():
    assert status({"broad_sources": {"muse": True}})["muse"]["on"]
    off = status({"broad_sources": {"muse": False}})["muse"]
    assert not off["on"] and "broad_sources.muse" in off["why"]


def test_missing_api_key_is_reported_as_the_reason_not_the_flag():
    # The flag is false BECAUSE there is no key; naming the flag would send the
    # reader to fix the wrong thing.
    s = status({"broad_sources": {"adzuna": False}})["adzuna"]
    assert not s["on"]
    assert "API key" in s["why"] and "adzuna_app_id" in s["why"]


def test_half_configured_key_still_counts_as_missing():
    s = status({"broad_sources": {"adzuna": True, "adzuna_app_id": "x"}})["adzuna"]
    assert not s["on"] and "adzuna_app_key" in s["why"]


def test_fully_keyed_source_is_on():
    s = status({"broad_sources": {"usajobs": True, "usajobs_email": "a@b.c",
                                  "usajobs_key": "k"}})["usajobs"]
    assert s["on"] and s["why"] == ""


# --- source_data ----------------------------------------------------------

RAW = [{"source": "greenhouse", "ok": True, "postings": 100},
       {"source": "greenhouse", "ok": False, "postings": 0},
       {"source": "muse", "ok": True, "postings": 40}]
JOBS = [{"_src": "greenhouse", "comp": "Acme"},
        {"_src": "greenhouse", "comp": "Acme"},
        {"_src": "muse", "comp": "Beta"}]


def sheet(declared=None, raw=RAW, jobs=JOBS):
    return {s["k"]: s for s in source_data(raw, jobs, declared)}


def test_counts_boards_failures_postings_roles_and_employers():
    s = sheet()["greenhouse"]
    assert (s["b"], s["f"], s["p"], s["m"], s["e"]) == (2, 1, 100, 2, 1)


def test_declared_but_silent_source_is_kept_with_its_reason():
    declared = [{"key": "adzuna", "name": "Adzuna", "kind": "broad", "url": "u",
                 "on": False, "why": "needs a free API key"}]
    s = sheet(declared)["adzuna"]
    assert not s["on"] and s["m"] == 0 and s["why"] == "needs a free API key"


def test_sources_absent_from_an_old_run_file_still_render():
    # Runs written before the run file carried a source list.
    assert set(sheet(None)) == {"greenhouse", "muse"}


def test_sorted_by_roles_delivered_then_live_sources_first():
    declared = [{"key": "adzuna", "name": "Adzuna", "kind": "broad", "url": "",
                 "on": False, "why": "off"},
                {"key": "lever", "name": "Lever", "kind": "board", "url": "",
                 "on": True, "why": ""}]
    assert [s["k"] for s in source_data(RAW, JOBS, declared)] == \
        ["greenhouse", "muse", "lever", "adzuna"]
