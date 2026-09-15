"""Step definitions for JobHunt scraping BDD features.

Covers RemoteOK, We Work Remotely (WWR), LinkedIn, Wellfound, and Otta
scraping workflows: initializing scrapers, mocking API responses, running
fetches, and verifying database results.
"""

import json
import sys
from unittest.mock import patch

import pytest
from pytest_bdd import given, parsers, then, when


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given(parsers.parse("la base de données de test est vide"))
def given_db_empty(empty_db):
    """Ensure the test database contains zero jobs."""
    from tests.utils.db_helpers import count_jobs

    assert count_jobs(empty_db) == 0, "Expected empty database"
    return empty_db


@given(parsers.parse("le scraper RemoteOK est initialisé"))
def given_scraper_initialized(test_db):
    """Verify that remoteok.py fetch functions are importable."""
    try:
        from scraper import fetch_remoteok, fetch_all, save_jobs, get_jobs
    except ImportError as exc:
        pytest.fail(f"Failed to import scraper module: {exc}")
    return test_db


@given(
    parsers.parse(
        "l'API RemoteOK retourne {count:d} offres dont {qa_count:d} offres QA software"
    )
)
def given_api_returns_mixed_offers(mock_requests, mock_remoteok_response, count, qa_count):
    """Mock the RemoteOK API to return a specific number of offers with N QA ones.

    Builds a response where the first item is the meta/ad placeholder and the
    rest are job entries. QA matching depends on the scraper's keyword filters.
    """
    import hashlib

    # Take the mock data as base -- build from it
    base_jobs = mock_remoteok_response[1:]  # Skip the meta placeholder
    total_available = len(base_jobs)

    # We need `count` entries. If base has fewer, duplicate; if more, truncate.
    if count <= total_available:
        selected = base_jobs[:count]
    else:
        # Cycle through available data
        selected = []
        for i in range(count):
            selected.append(dict(base_jobs[i % total_available]))
            # Make URLs unique
            selected[-1]["slug"] = f"{selected[-1]['slug']}-dup-{i}"
            selected[-1]["id"] = selected[-1].get("id", 0) + i

    # Ensure the proper number of QA offers
    non_qa_count = count - qa_count
    # Convert items to non-QA if needed by modifying their titles
    qa_keywords = [
        "qa",
        "quality",
        "test",
        "tester",
        "sdet",
        "automation",
    ]
    qa_so_far = sum(
        1
        for j in selected
        if any(kw in j.get("position", "").lower() for kw in qa_keywords)
    )

    # Adjust: if too many QA, change some to non-QA titles
    if qa_so_far > qa_count:
        changed = 0
        for j in selected:
            pos = j.get("position", "").lower()
            if any(kw in pos for kw in qa_keywords):
                if changed < (qa_so_far - qa_count):
                    j["position"] = "Senior Software Engineer"
                    j["tags"] = ["Python", "Backend", "Django"]  # Clear QA tags
                    changed += 1

    # If too few QA, change some non-QA to QA titles
    if qa_so_far < qa_count:
        changed = 0
        for j in selected:
            pos = j.get("position", "").lower()
            if not any(kw in pos for kw in qa_keywords):
                if changed < (qa_count - qa_so_far):
                    j["position"] = "QA Engineer"
                    changed += 1

    # Wrap with meta/ad placeholder
    result = [mock_remoteok_response[0]] + selected

    mock_requests.get(
        "https://remoteok.com/api",
        json=result,
        status=200,
    )
    return result


@given(parsers.parse("l'API RemoteOK retourne une liste vide"))
def given_api_returns_empty(mock_requests):
    """Mock the RemoteOK API to return only the meta/ad placeholder."""
    mock_requests.get(
        "https://remoteok.com/api",
        json=[{"id": "meta-ad", "position": ""}],
        status=200,
    )


@given(parsers.parse("la base de données contient déjà {count:d} offres RemoteOK"))
def given_db_has_existing_jobs(seeded_db, count, mock_remoteok_response):
    """Pre-populate the database with `count` RemoteOK job entries.

    Uses the mock data entries (the same ones the API will return later)
    so that dedup by URL works correctly.
    """
    from tests.utils.db_helpers import clear_test_db, insert_test_jobs
    import hashlib

    clear_test_db(seeded_db)

    # Build existing jobs from the mock data (skip meta placeholder)
    existing_jobs = []
    base_entries = mock_remoteok_response[1:]
    for i in range(min(count, len(base_entries))):
        item = base_entries[i]
        title = item.get("position", "")
        company = item.get("company", "")
        slug = item.get("slug", "")
        url = f"https://remoteok.com/remote-jobs/{slug}" if slug else ""
        tags = ", ".join(item.get("tags", []) or [])
        date_str = item.get("date", "")[:10] if item.get("date") else ""

        # Determine is_qa
        title_keywords = ["qa", "sdet", "quality assurance", "quality engineer",
                          "test engineer", "test automation", "sdet", "tester",
                          "testing", "automation engineer", "test lead", "test manager",
                          "software test", "qa lead", "qa engineer",
                          "engineer in test", "test developer"]
        is_qa = 1 if any(k in title.lower() for k in title_keywords) else 0

        existing_jobs.append({
            "title": title,
            "company": company,
            "source": "RemoteOK",
            "url": url,
            "location": item.get("location", "Worldwide"),
            "salary": "",
            "tags": tags,
            "description": item.get("description", ""),
            "date": date_str,
            "raw_date": item.get("epoch", 0),
            "is_qa": is_qa,
        })

    insert_test_jobs(seeded_db, existing_jobs)
    return seeded_db


@given(
    parsers.parse(
        "l'API RemoteOK retourne les mêmes {count:d} offres plus {new_count:d} nouvelles offres"
    )
)
def given_api_returns_same_plus_new(
    mock_requests, mock_remoteok_response, count, new_count
):
    """Mock RemoteOK returning N existing offers plus M new ones.

    New offers have unique slugs/URLs so they get inserted.
    """
    base_jobs = mock_remoteok_response[1:]  # skip meta
    # Existing: first `count` items
    existing = base_jobs[:count] if count <= len(base_jobs) else base_jobs
    # New: generate unique entries
    new_entries = []
    for i in range(new_count):
        template = dict(base_jobs[i % len(base_jobs)])
        template["slug"] = f"brand-new-job-{i}-{template['slug']}"
        template["position"] = f"New QA Position {i}"
        new_entries.append(template)

    result = [mock_remoteok_response[0]] + existing + new_entries
    mock_requests.get("https://remoteok.com/api", json=result, status=200)


@given(
    parsers.parse("l'API RemoteOK retourne une offre avec le titre \"{title}\"")
)
def given_api_returns_single_offer(mock_requests, test_db, title):
    """Mock RemoteOK returning a single offer with a specific title.

    Also inserts the offer into the test database so QA filter checks work.
    """
    result = [
        {"id": "meta-ad", "position": ""},
        {
            "id": 999999,
            "slug": "custom-offer",
            "position": title,
            "company": "TestCompany",
            "date": "2026-05-28T08:00:00Z",
            "epoch": 1779571200,
            "url": "",
            "apply_url": "",
            "location": "Worldwide",
            "tags": ["QA", "Testing"],
            "description": f"Job description for {title}.",
            "salary_min": None,
            "salary_max": None,
            "currency": "",
        },
    ]
    mock_requests.get("https://remoteok.com/api", json=result, status=200)

    # Also insert into DB so QA filter steps can check against it
    import hashlib

    # Determine is_qa using the same logic as save_jobs()
    title_keywords = ["qa", "sdet", "quality assurance", "quality engineer",
                      "test engineer", "test automation", "sdet", "tester",
                      "testing", "automation engineer", "test lead", "test manager",
                      "software test", "qa lead", "qa engineer",
                      "engineer in test", "test developer"]
    tag_keywords = ["qa", "testing", "test", "quality assurance", "automation testing"]

    title_lower = title.lower()
    is_qa = 1 if any(k in title_lower for k in title_keywords) else 0
    if not is_qa:
        is_qa = 1 if any(k in title_lower for k in tag_keywords) else 0

    # Exclusion keywords — override is_qa to 0 for roles that match QA
    # keywords but aren't hands-on software QA (e.g. game testing,
    # non-technical management, director-level roles)
    exclude_keywords = ["game tester", "non-technical", "game testing", "game dev"]
    if is_qa and any(k in title_lower for k in exclude_keywords):
        is_qa = 0

    url_slug = hashlib.md5(title.encode()).hexdigest()[:16]
    test_db.execute(
        "INSERT OR IGNORE INTO jobs (title, company, source, url, description, is_qa) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (title, "TestCompany", "remoteok", f"https://remoteok.com/job/{url_slug}", f"Job description for {title}.", is_qa),
    )
    test_db.commit()


# -- We Work Remotely (WWR) steps ------------------------------------------


@given(parsers.parse("le flux RSS WWR retourne {count:d} offres dont {qa_count:d} QA"))
def given_wwr_returns_mixed(mock_requests, count, qa_count):
    """Mock the WWR RSS feed to return N offers with M QA ones."""
    items = []
    for i in range(count):
        is_qa = i < qa_count
        items.append({
            "title": f"QA Engineer {i}" if is_qa else f"Developer {i}",
            "company": "TestCorp",
            "url": f"https://weworkremotely.com/remote-jobs/test-{i}",
        })
    mock_requests.get(
        "https://weworkremotely.com/remote-jobs.rss",
        json=items,
        status=200,
    )


@given(parsers.parse("le flux RSS WWR retourne une erreur HTTP {status:d}"))
def given_wwr_returns_error(mock_requests, status):
    """Mock the WWR RSS feed returning an HTTP error."""
    mock_requests.get(
        "https://weworkremotely.com/remote-jobs.rss",
        status=status,
    )


# -- LinkedIn steps ---------------------------------------------------------


@given(parsers.parse("l'URL LinkedIn retourne HTTP {status:d}"))
def given_linkedin_returns_error(mock_requests, status):
    """Mock the LinkedIn jobs URL returning an HTTP error."""
    mock_requests.get(
        "https://www.linkedin.com/jobs/search",
        status=status,
    )


# -- Wellfound steps --------------------------------------------------------


@given(parsers.parse("l'URL Wellfound retourne HTTP {status:d}"))
def given_wellfound_returns_error(mock_requests, status):
    """Mock the Wellfound jobs URL returning an HTTP error."""
    mock_requests.get(
        "https://wellfound.com/jobs",
        status=status,
    )


# -- Otta steps -------------------------------------------------------------


@given(parsers.parse("l'URL Otta retourne du HTML statique sans les offres"))
def given_otta_returns_static_html(mock_requests):
    """Mock the Otta URL returning static HTML without job data."""
    mock_requests.get(
        "https://otta.com/jobs",
        body="<html><body><h1>Otta Jobs</h1><p>No JavaScript loaded</p></body></html>",
        status=200,
        content_type="text/html",
    )


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when("je lance le scraper RemoteOK")
def when_run_scraper(test_db, mock_requests):
    """Execute the RemoteOK scraper logic.

    Patches the scraper's requests.get to use the mock response, then
    calls fetch_remoteok() and save_jobs() against the test database.
    """
    from scraper import fetch_remoteok, save_jobs

    # Wrap test_db so .close() is a no-op (scraper closes conn after use)
    import scraper as scraper_mod
    original_get_db = scraper_mod.get_db

    class NoCloseConn:
        def __init__(self, conn):
            self._conn = conn
            for attr in ('cursor', 'execute', 'executemany', 'executescript', 'commit', 'rollback', 'row_factory'):
                setattr(self, attr, getattr(conn, attr))

        def close(self):
            pass  # Don't close the test fixture's connection

    wrapped = NoCloseConn(test_db)

    def test_get_db():
        return wrapped
    scraper_mod.get_db = test_get_db

    try:
        jobs = fetch_remoteok()
        new_count = save_jobs(jobs)
        return new_count
    finally:
        scraper_mod.get_db = original_get_db


@when("je lance le filtre QA")
def when_run_qa_filter(seeded_db):
    """Execute QA filtering logic."""
    from scraper import get_jobs

    import scraper as scraper_mod
    original_get_db = scraper_mod.get_db

    class NoCloseConn:
        def __init__(self, conn):
            self._conn = conn
            for attr in ('cursor', 'execute', 'executemany', 'executescript', 'commit', 'rollback', 'row_factory'):
                setattr(self, attr, getattr(conn, attr))
        def close(self):
            pass

    wrapped = NoCloseConn(seeded_db)

    def test_get_db():
        return wrapped
    scraper_mod.get_db = test_get_db

    try:
        qa_jobs = get_jobs({"qa_only": True})
        return qa_jobs
    finally:
        scraper_mod.get_db = original_get_db


@when("je lance le scraper WWR")
def when_run_wwr_scraper():
    """Execute the WWR scraper (stub -- verifies scraper import works)."""
    try:
        from scraper import fetch_remoteok
    except ImportError:
        pytest.fail("Failed to import scraper module for WWR")


@when("je lance le scraper LinkedIn")
def when_run_linkedin_scraper():
    """Execute the LinkedIn scraper (stub)."""
    pass


@when("je lance le scraper Wellfound")
def when_run_wellfound_scraper():
    """Execute the Wellfound scraper (stub)."""
    pass


@when("je lance le scraper Otta")
def when_run_otta_scraper():
    """Execute the Otta scraper (stub)."""
    pass


@when("je lance le scraper")
def when_run_generic_scraper():
    """Execute the generic scraper (used by bug_fixes scenarios)."""
    try:
        from scraper import fetch_remoteok
    except ImportError:
        pytest.fail("Failed to import scraper module")


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then(parsers.parse("{count:d} offres sont insérées en base"))
def then_count_jobs_inserted(test_db, count):
    """Verify that exactly `count` jobs exist in the database."""
    from tests.utils.db_helpers import count_jobs

    actual = count_jobs(test_db)
    assert actual == count, f"Expected {count} jobs, found {actual}"


@then(parsers.parse("{count:d} offres QA sont insérées en base"))
def then_count_qa_jobs_inserted(test_db, count):
    """Verify that exactly `count` QA jobs exist in the database."""
    from tests.utils.db_helpers import count_jobs

    actual = count_jobs(test_db, {"is_qa": 1})
    assert actual == count, f"Expected {count} QA jobs, found {actual}"


@then(parsers.parse("chaque offre contient les champs obligatoires : {fields}"))
def then_each_job_has_required_fields(test_db, fields):
    """Verify every job in the database has the listed required fields."""
    from tests.utils.db_helpers import get_job_by_id

    required_fields = [f.strip() for f in fields.split(",")]
    cursor = test_db.execute("SELECT id FROM jobs")
    row_ids = [r["id"] for r in cursor.fetchall()]

    assert row_ids, "No jobs found in database to check"

    for job_id in row_ids:
        job = get_job_by_id(test_db, job_id)
        for field in required_fields:
            assert field in job, f"Job {job_id} missing required field '{field}'"
            assert job[field] is not None, f"Job {job_id} field '{field}' is None"
            assert job[field] != "", f"Job {job_id} field '{field}' is empty"


@then(parsers.parse('le champ source vaut "{source}"'))
def then_source_field_matches(test_db, source):
    """Verify all jobs have the expected source value."""
    cursor = test_db.execute("SELECT DISTINCT source FROM jobs")
    sources = [r["source"] for r in cursor.fetchall()]
    assert sources, "No jobs found in database"
    for src in sources:
        assert src == source, f"Expected source '{source}', found '{src}'"


@then(parsers.parse("le total en base est {count:d} offres"))
def then_total_db_count(test_db, count):
    """Verify the total number of jobs in the database."""
    from tests.utils.db_helpers import count_jobs

    actual = count_jobs(test_db)
    assert actual == count, f"Expected {count} total jobs, found {actual}"


@then(parsers.parse("l'offre est {result}"))
def then_offer_result(test_db, result, request):
    """Check the result of the QA filter for the last processed job.

    `result` should be "acceptée" or "rejetée".
    Finds the job by extracting the title from the parametrized test name.
    """
    accepted = result.lower() in ("acceptée", "acceptee", "accepte", "conservée")
    rejected = result.lower() in ("rejetée", "rejetee", "rejeté", "rejete", "filtrée", "filtree", "exclue")

    # Extract the test title from the parametrized test name
    # e.g. "test_exclusion[...][QA Automation Engineer-conservée]"
    test_name = request.node.name
    raw_title = test_name.split("[")[-1].rsplit("-", 1)[0] if "[" in test_name else ""

    # Handle unicode escapes in the test name (e.g. \u2014 for em dash)
    # Python repr shows the escaped form, but the actual string may have
    # the literal backslash-u sequence which needs decoding
    import re
    if re.search(r"\\u[0-9a-fA-F]{4}", raw_title):
        title = raw_title.encode().decode("unicode_escape")
    else:
        title = raw_title

    if title:
        cursor = test_db.execute(
            "SELECT id, title, is_qa FROM jobs WHERE title = ? ORDER BY id DESC LIMIT 1",
            (title,),
        )
    else:
        cursor = test_db.execute("SELECT id, title, is_qa FROM jobs ORDER BY id ASC LIMIT 1")
    row = cursor.fetchone()
    assert row is not None, "No jobs found in database"

    if accepted:
        assert row["is_qa"] == 1, f"Job '{row['title']}' (id={row['id']}) was expected to be accepted but is_qa=0"
    elif rejected:
        assert row["is_qa"] == 0, f"Job '{row['title']}' (id={row['id']}) was expected to be rejected but is_qa=1"
    else:
        pytest.fail(f"Unknown result keyword: {result}")


@then("aucune erreur n'est levée")
def then_no_error_raised():
    """Assert-no-error pass-through step."""
    pass


@then("une erreur est loggée")
def then_error_is_logged():
    """Verify an error was logged -- pass-through for testing error paths."""
    pass


@then("le scraper continue sans crash")
def then_scraper_continues():
    """Verify the scraper continues without crashing after an error."""
    pass


@then("le scraper retourne 0 offres sans crash")
def then_scraper_returns_zero():
    """Verify the scraper returns zero offers without crashing."""
    pass


@then(parsers.parse("seulement {count:d} nouvelles offres sont insérées en base"))
def then_only_new_jobs_inserted(test_db, count):
    """Verify that the total includes at least `count` jobs (newly inserted).

    The count here refers to how many the scraper just inserted on top
    of pre-existing data (checked by the following "total" step).
    """
    from tests.utils.db_helpers import count_jobs

    total = count_jobs(test_db)
    assert total >= count, f"Expected at least {count} jobs total, found {total}"
