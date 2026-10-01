"""Parsers for the board sources that have no JSON API of their own."""
from fetch import _display, parse_jazzhr, parse_successfactors, parse_talentbrew

SF_PAGE = """
<span class="paginationLabel">Results <b>1 – 25</b> of <b>294</b></span>
<tr class="data-row">
  <td class="colTitle"><span class="jobTitle hidden-phone">
    <a href="/job/San-Diego-ISSO-CA-92127/1406902200/" class="jobTitle-link">Junior/Mid-Level ISSO</a>
  </span></td>
  <td class="colLocation"><span class="jobLocation">
      San Diego, CA, US, 92127
  </span></td>
  <td class="colDate"><span class="jobDate">Sep 4, 2026
  </span></td>
</tr>
"""


def test_successfactors_row():
    jobs, total = parse_successfactors(SF_PAGE, "careers.leonardodrs.com")
    assert total == 294
    (j,) = jobs
    assert j["id"] == "successfactors:careers.leonardodrs.com:1406902200"
    assert j["title"] == "Junior/Mid-Level ISSO"
    assert j["location"] == "San Diego, CA, US"
    assert j["posted"] == "2026-09-04"
    assert j["url"] == j["detail_url"] == \
        "https://careers.leonardodrs.com/job/San-Diego-ISSO-CA-92127/1406902200/"
    assert j["company"] == "Leonardo DRS"


TB_FRAGMENT = """
<section data-total-results="2218" data-total-pages="23">
<li>
  <a href="/en/job/palm-bay/cyber-engineer/4832/101404699024" data-job-id="101404699024">
    <h2>Cyber Engineer</h2>
    <span class="results-facet job-category">Engineering</span>
    <span class="results-facet job-location test3">Palm Bay, FL</span>
  </a>
</li>
</section>
"""


def test_talentbrew_item():
    jobs, pages = parse_talentbrew(TB_FRAGMENT, "careers.l3harris.com/en")
    assert pages == 23
    (j,) = jobs
    assert j["id"] == "talentbrew:careers.l3harris.com:101404699024"
    assert j["title"] == "Cyber Engineer" and j["location"] == "Palm Bay, FL"
    assert j["url"] == \
        "https://careers.l3harris.com/en/job/palm-bay/cyber-engineer/4832/101404699024"
    assert j["company"] == "L3Harris"


JAZZ_FEED = """<?xml version="1.0" encoding="utf-8"?>
<jobs>
  <company><![CDATA[Alluvionic]]></company>
  <job>
    <id><![CDATA[job_20260922164316_6XYL1D8DYI42CQOV]]></id>
    <status><![CDATA[Open]]></status>
    <title><![CDATA[Cybersecurity Analyst II]]></title>
    <url><![CDATA[https://alluvionic.applytojob.com/apply/abc/Cyber]]></url>
    <city><![CDATA[Melbourne]]></city>
    <state><![CDATA[FL]]></state>
    <country><![CDATA[United States]]></country>
    <type><![CDATA[Full Time]]></type>
    <description><![CDATA[<p>Monitor <b>SIEM</b> alerts.</p>]]></description>
  </job>
  <job>
    <id><![CDATA[job_20260101000000_X]]></id>
    <status><![CDATA[Closed]]></status>
    <title><![CDATA[Old Role]]></title>
  </job>
</jobs>"""


def test_jazzhr_feed_keeps_open_jobs_and_dates_them_from_the_id():
    (j,) = parse_jazzhr(JAZZ_FEED, "alluvionic")
    assert j["id"] == "jazzhr:alluvionic:job_20260922164316_6XYL1D8DYI42CQOV"
    assert j["company"] == "Alluvionic" and j["title"] == "Cybersecurity Analyst II"
    assert j["location"] == "Melbourne, FL" and j["posted"] == "2026-09-22"
    assert j["description"] == "Monitor SIEM alerts."


def test_defence_workday_tenants_have_readable_names():
    assert _display("ngc") == "Northrop Grumman"
    assert _display("bah") == "Booz Allen Hamilton"
    assert _display("globalhr") == "RTX (Collins Aerospace)"
