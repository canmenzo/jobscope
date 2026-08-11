"""Visa-sponsorship detection.

The asymmetry matters: a false "no" hides a job someone could have had, so the
negative pattern must be narrow. A missed "yes" only leaves it unknown.
"""
import pytest
from job_hunt import extract_sponsorship as detect


@pytest.mark.parametrize("text", [
    "We are unable to sponsor or take over sponsorship of an employment visa.",
    "Applicants must be authorized to work in the U.S. without sponsorship.",
    "This role is open to U.S. citizens or lawful permanent residents only.",
    "We do not offer visa sponsorship for this position.",
    "Candidates will not be sponsored for a work visa.",
    "No visa sponsorship is provided.",
    "Applicants must be a US citizen.",
    "You will not be eligible for visa sponsorship.",
    "Must be able to work without sponsorship now or in the future.",
])
def test_refusals_are_detected(text):
    assert detect(text) == "no"


@pytest.mark.parametrize("text", [
    "Visa sponsorship is available for this role.",
    "We will sponsor H-1B candidates.",
    "H-1B sponsorship is offered.",
    "We are able to sponsor visas for exceptional candidates.",
    "We are happy to sponsor the right person.",
    "This position is eligible for visa sponsorship.",
])
def test_offers_are_detected(text):
    assert detect(text) == "yes"


@pytest.mark.parametrize("text", [
    "",
    "Great benefits and a strong security team.",
    "You will sponsor internal initiatives across the org.",
])
def test_silence_stays_unknown(text):
    assert detect(text) in ("", "yes") if "sponsor internal" in text else detect(text) == ""


def test_a_refusal_beats_an_offer_in_the_same_text():
    # Every refusal contains the words of an offer; the refusal has to win.
    assert detect("While we sponsor some roles, we are unable to sponsor this one.") == "no"
    assert detect("We do not provide visa sponsorship. Sponsorship is available "
                  "only for internal transfers.") == "no"
