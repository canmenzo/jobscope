"""Salary and years-of-experience extraction from free-text descriptions."""
import pytest
from job_hunt import extract_salary, extract_yoe


@pytest.mark.parametrize("desc,expected", [
    ("The range is $140,000 - $180,000 per year.", "$140K–$180K"),
    ("Base pay $140k–$180K", "$140K–$180K"),
    ("$140,000 to $180,000", "$140K–$180K"),
    ("Compensation: $95,000-$120,000 USD", "$95K–$120K"),
])
def test_extract_salary_formats(desc, expected):
    assert extract_salary(desc) == expected


@pytest.mark.parametrize("desc", [
    "",
    "A $175 monthly stipend and a $50 - $75 lunch budget.",  # too small to be salary
    "We offer competitive compensation.",
    "Equity between $2,000,000 - $4,000,000 in notional value.",  # too large
])
def test_extract_salary_rejects_noise(desc):
    assert extract_salary(desc) == ""


def test_extract_salary_takes_first_plausible_range():
    assert extract_salary("Perks up to $10 - $20 daily. Salary $150,000 - $170,000.") \
        == "$150K–$170K"


# --- years of experience --------------------------------------------------

@pytest.mark.parametrize("desc,expected", [
    ("5+ years of experience in security operations", 5),
    ("3-5 years of relevant experience", 3),
    ("Minimum 8 years experience required", 8),
    ("2 years of professional experience with Python", 2),
    ("10+ years experience", 10),
])
def test_extract_yoe_patterns(desc, expected):
    assert extract_yoe(desc) == expected


def test_extract_yoe_takes_the_lowest_stated_bar():
    # "3+ required, 8+ preferred" has a real bar of 3 — under-report rather
    # than wrongly mark a reachable role as out of range.
    desc = "8+ years of experience preferred. 3+ years of experience required."
    assert extract_yoe(desc) == 3


@pytest.mark.parametrize("desc", [
    "",
    "We have been in business for 30 years.",       # no 'experience' nearby
    "A great experience for the right person.",     # no number
    "Founded 2011, 40 years of combined leadership across the team and beyond "
    "with deep experience",                         # >20 filtered out
])
def test_extract_yoe_rejects_noise(desc):
    assert extract_yoe(desc) is None


def test_extract_yoe_ignores_implausible_values():
    assert extract_yoe("99 years of experience") is None
