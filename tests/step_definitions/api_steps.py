"""Step definitions for JobHunt API endpoint BDD features.

Covers all REST API endpoints: listing jobs, stats, saving, applying,
updating pipeline, saving notes, enrichment trigger, and refresh.

Uses the api_client fixture and a simple dictionary fixture to pass the
last API response between steps.
"""

import json

import pytest
from pytest_bdd import given, parsers, then, when


# ---------------------------------------------------------------------------
# Helper fixture to share state between steps
# ---------------------------------------------------------------------------


@pytest.fixture
def api_response():
    """Simple dict to store the last API response between steps."""
    return {}


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given("la base de données est initialisée avec des données de test")
def given_db_init_with_test_data(seeded_db):
    """seeded_db fixture pre-populates with sample data."""
    from tests.utils.db_helpers import count_jobs

    assert count_jobs(seeded_db) > 0, "No data in seeded database"
    return seeded_db


@given("l'API est accessible")
def given_api_accessible(api_client):
    """Verify the Flask test client is functional."""
    response = api_client.client.get("/")
    assert response.status_code in (200, 302), f"API not accessible: {response.status_code}"
    return api_client


@given(parsers.parse("une offre avec ID {job_id:d} existe"))
def given_job_exists(seeded_db, job_id):
    """Ensure a specific job ID exists in the database."""
    from tests.utils.db_helpers import get_job_by_id

    job = get_job_by_id(seeded_db, job_id)
    if job is None:
        pytest.skip(f"Job with ID {job_id} not found in seeded data")
    return job


@given(parsers.parse('une offre avec ID {job_id:d} est déjà marquée "{status}"'))
def given_job_with_status(seeded_db, job_id, status):
    """Mark a job with a specific pipeline status."""
    from tests.utils.db_helpers import get_job_by_id

    job = get_job_by_id(seeded_db, job_id)
    if job is None:
        pytest.skip(f"Job with ID {job_id} not found")

    seeded_db.execute("UPDATE jobs SET applied = 1 WHERE id = ?", (job_id,))
    seeded_db.execute(
        "INSERT OR REPLACE INTO applications (job_id, status) VALUES (?, ?)",
        (job_id, status),
    )
    seeded_db.commit()


# -- API endpoint Given steps (jobs, stats, saved) -------------------------


@given("le serveur Flask tourne sur localhost:5050")
def given_flask_running():
    """Verify the Flask app is importable and configured."""
    try:
        import app as app_module
    except ImportError as exc:
        pytest.fail(f"Failed to import Flask app: {exc}")


@given("la base de données contient 20 offres de test")
def given_db_has_20_test_offers(seeded_db, sample_jobs):
    """Verify the seeded database has at least 20 jobs."""
    from tests.utils.db_helpers import count_jobs

    actual = count_jobs(seeded_db)
    if actual < 20:
        pytest.skip(f"Need 20 jobs but only {actual} available")


@given(parsers.parse('{count:d} offres contiennent "{tech}" dans tech_stack'))
def given_n_offers_with_tech(seeded_db, count, tech):
    """Mark N jobs with the given tech in their tech_stack field."""
    import json as _json

    cursor = seeded_db.execute("SELECT id FROM jobs LIMIT ?", (count,))
    ids = [r["id"] for r in cursor.fetchall()]
    for job_id in ids:
        seeded_db.execute(
            "UPDATE jobs SET tech_stack = ? WHERE id = ?",
            (_json.dumps([tech]), job_id),
        )
    seeded_db.commit()


@given("la base contient 10 offres avec seniority variés")
def given_db_with_varied_seniority(seeded_db):
    """Ensure at least 10 jobs with varied seniority levels."""
    from tests.utils.db_helpers import count_jobs

    actual = count_jobs(seeded_db)
    if actual < 10:
        pytest.skip(f"Need 10 jobs but only {actual} available")
    # Assign varied seniority
    levels = ["junior", "mid", "senior", "lead", "senior"]
    cursor = seeded_db.execute("SELECT id FROM jobs LIMIT 10")
    ids = [r["id"] for r in cursor.fetchall()]
    for idx, job_id in enumerate(ids):
        seeded_db.execute(
            "UPDATE jobs SET seniority = ? WHERE id = ?",
            (levels[idx % len(levels)], job_id),
        )
    seeded_db.commit()


@given(parsers.parse("l'offre avec id={job_id:d} a saved = {saved_val:d}"))
def given_job_saved_status(seeded_db, job_id, saved_val):
    """Set the saved field on a specific job."""
    from tests.utils.db_helpers import get_job_by_id

    job = get_job_by_id(seeded_db, job_id)
    if job is None:
        pytest.skip(f"Job with ID {job_id} not found")
    seeded_db.execute("UPDATE jobs SET saved = ? WHERE id = ?", (saved_val, job_id))
    seeded_db.commit()


@given(parsers.parse("{count:d} offres sont sauvegardées"))
def given_n_saved_offers(seeded_db, count):
    """Mark N jobs as saved."""
    cursor = seeded_db.execute("SELECT id FROM jobs LIMIT ?", (count,))
    ids = [r["id"] for r in cursor.fetchall()]
    for job_id in ids:
        seeded_db.execute("UPDATE jobs SET saved = 1 WHERE id = ?", (job_id,))
    seeded_db.commit()


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when("je récupère la liste des offres")
def when_get_jobs_list(api_client, api_response):
    """GET /api/jobs."""
    api_response["last"] = api_client.get_jobs()


@when("je récupère les statistiques")
def when_get_stats(api_client, api_response):
    """GET /api/stats."""
    api_response["last"] = api_client.get_stats()


@when(parsers.parse("je sauvegarde l'offre avec ID {job_id:d}"))
def when_save_job(api_client, api_response, job_id):
    """POST /api/jobs/<id>/save."""
    api_response["last"] = api_client.save_job(job_id)


@when(parsers.parse("je postule à l'offre avec ID {job_id:d}"))
def when_apply_job(api_client, api_response, job_id):
    """POST /api/jobs/<id>/apply."""
    api_response["last"] = api_client.apply_job(job_id)


@when(parsers.parse("je postule à l'offre avec ID {job_id:d} avec le statut \"{status}\""))
def when_apply_job_with_status(api_client, api_response, job_id, status):
    """POST /api/jobs/<id>/apply with explicit status."""
    api_response["last"] = api_client.apply_job(job_id, status=status)


@when(parsers.parse("je mets à jour les notes de l'offre avec ID {job_id:d}"))
def when_update_notes(api_client, api_response, job_id):
    """POST /api/jobs/<id>/notes."""
    api_response["last"] = api_client.update_notes(job_id, "Test notes for this job")


@when(parsers.parse("je mets à jour le pipeline de l'offre avec ID {job_id:d} vers \"{status}\""))
def when_update_pipeline(api_client, api_response, job_id, status):
    """POST /api/jobs/<id>/pipeline."""
    api_response["last"] = api_client.update_pipeline(job_id, status)


@when("je déclenche un rafraîchissement")
def when_trigger_refresh(api_client, api_response):
    """GET /refresh or POST /api/refresh."""
    api_response["last"] = api_client.trigger_refresh()


# -- API endpoint When steps (jobs, stats, saved) --------------------------


@when("j'envoie une requête GET sur /api/jobs")
def when_get_api_jobs(api_client, api_response):
    """GET /api/jobs."""
    api_response["last"] = api_client.get_jobs()


@when(parsers.parse("j'envoie GET /api/jobs?tech={tech}"))
def when_get_api_jobs_with_tech(api_client, api_response, tech):
    """GET /api/jobs with tech filter."""
    api_response["last"] = api_client.get_jobs({"tech": tech})


@when("j'envoie une requête GET sur /api/stats")
def when_get_api_stats(api_client, api_response):
    """GET /api/stats."""
    api_response["last"] = api_client.get_stats()


@when("j'envoie GET /api/stats/advanced")
def when_get_api_stats_advanced(api_client, api_response):
    """GET /api/stats/advanced."""
    api_response["last"] = api_client.client.get("/api/stats/advanced")


@when(parsers.parse("j'envoie POST /api/jobs/{job_id:d}/save"))
def when_post_api_jobs_save(api_client, api_response, job_id):
    """POST /api/jobs/<id>/save."""
    api_response["last"] = api_client.save_job(job_id)


@when("j'envoie GET /api/jobs/saved")
def when_get_api_jobs_saved(api_client, api_response):
    """GET /api/jobs/saved."""
    api_response["last"] = api_client.client.get("/api/jobs/saved")


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then("le statut HTTP est 200")
def then_status_200(api_response):
    """Verify the last API response has status 200."""
    resp = api_response.get("last")
    assert resp is not None, "No API response stored"
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"


@then("le statut HTTP est 201")
def then_status_201(api_response):
    """Verify the last API response has status 201."""
    resp = api_response.get("last")
    assert resp is not None, "No API response stored"
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}"


@then("le statut HTTP est 404")
def then_status_404(api_response):
    """Verify the last API response has status 404."""
    resp = api_response.get("last")
    assert resp is not None, "No API response stored"
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"


@then(parsers.parse("le statut HTTP est {status:d}"))
def then_status_n(api_response, status):
    """Verify the last API response has a given HTTP status."""
    resp = api_response.get("last")
    assert resp is not None, "No API response stored"
    assert resp.status_code == status, (
        f"Expected {status}, got {resp.status_code}"
    )


@then("la réponse contient une liste d'offres")
def then_response_contains_jobs(api_response):
    """Verify response body is a JSON list of jobs."""
    resp = api_response.get("last")
    assert resp is not None, "No API response stored"
    data = json.loads(resp.data.decode("utf-8"))
    assert isinstance(data, list), f"Expected list, got {type(data)}"
    assert len(data) > 0, "Empty list returned"


@then("la réponse contient les statistiques")
def then_response_contains_stats(api_response):
    """Verify response body has expected stats keys."""
    resp = api_response.get("last")
    assert resp is not None, "No API response stored"
    data = json.loads(resp.data.decode("utf-8"))
    assert isinstance(data, dict), f"Expected dict, got {type(data)}"
    expected_keys = {"total", "qa", "applied", "companies"}
    assert expected_keys.issubset(data.keys()), (
        f"Missing stats keys. Expected {expected_keys}, got {set(data.keys())}"
    )


@then("l'offre est marquée comme sauvegardée")
def then_job_saved(api_response):
    """Verify the save response indicates success."""
    resp = api_response.get("last")
    assert resp is not None, "No API response stored"
    data = json.loads(resp.data.decode("utf-8"))
    assert data.get("status") == "ok", f"Unexpected response: {data}"


@then("l'offre est marquée comme postulée")
def then_job_applied(api_response):
    """Verify applied response indicates success."""
    resp = api_response.get("last")
    assert resp is not None, "No API response stored"
    data = json.loads(resp.data.decode("utf-8"))
    assert data.get("status") == "ok", f"Unexpected response: {data}"


@then(parsers.parse('le pipeline a le statut "{status}"'))
def then_pipeline_status(api_response, status):
    """Verify the pipeline status in the API response."""
    resp = api_response.get("last")
    assert resp is not None, "No API response stored"
    data = json.loads(resp.data.decode("utf-8"))
    assert data.get("status") == "ok", f"Unexpected response: {data}"
    if "pipeline_status" in data:
        assert data["pipeline_status"] == status, (
            f"Expected pipeline status '{status}', got '{data['pipeline_status']}'"
        )


@then("la réponse est un JSON valide")
def then_response_valid_json(api_response):
    """Verify the response body is parseable JSON."""
    resp = api_response.get("last")
    assert resp is not None, "No API response stored"
    try:
        json.loads(resp.data.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        pytest.fail(f"Invalid JSON response: {exc}")


# -- API endpoint Then steps (jobs, stats, saved) --------------------------


@then(parsers.parse('le Content-Type est "{content_type}"'))
def then_content_type(api_response, content_type):
    """Verify the response Content-Type header."""
    resp = api_response.get("last")
    assert resp is not None, "No API response stored"
    actual = resp.content_type
    assert actual == content_type, f"Expected Content-Type '{content_type}', got '{actual}'"


@then(parsers.parse("la réponse contient {count:d} offres"))
def then_response_has_n_jobs(api_response, count):
    """Verify the response contains exactly N offers."""
    resp = api_response.get("last")
    assert resp is not None, "No API response stored"
    data = json.loads(resp.data.decode("utf-8"))
    actual = len(data) if isinstance(data, list) else data.get("total", data.get("count", -1))
    assert actual == count, f"Expected {count} jobs in response, got {actual}"


@then(parsers.parse("la réponse contient total_jobs, jobs_this_week, avg_salary"))
def then_response_contains_stats_fields(api_response):
    """Verify the response contains specific stats fields."""
    resp = api_response.get("last")
    assert resp is not None, "No API response stored"
    data = json.loads(resp.data.decode("utf-8"))
    for field in ["total_jobs", "jobs_this_week", "avg_salary"]:
        assert field in data, f"Field '{field}' not found in response. Keys: {list(data.keys())}"
        assert data[field] is not None, f"Field '{field}' is None"


@then(parsers.parse('la réponse contient "{key}"'))
def then_response_contains_key(api_response, key):
    """Verify the response JSON contains a specific key."""
    resp = api_response.get("last")
    assert resp is not None, "No API response stored"
    data = json.loads(resp.data.decode("utf-8"))
    assert key in data, f"Key '{key}' not found in response. Keys: {list(data.keys())}"


@then(parsers.parse('"{key}" est présent'))
def then_key_is_present(api_response, key):
    """Verify a key is present in the response JSON."""
    resp = api_response.get("last")
    assert resp is not None, "No API response stored"
    data = json.loads(resp.data.decode("utf-8"))
    assert key in data, f"Key '{key}' not found in response. Keys: {list(data.keys())}"


@then(parsers.parse('"{key}" est un tableau'))
def then_key_is_array(api_response, key):
    """Verify a key in the response JSON is an array."""
    resp = api_response.get("last")
    assert resp is not None, "No API response stored"
    data = json.loads(resp.data.decode("utf-8"))
    assert key in data, f"Key '{key}' not found in response"
    assert isinstance(data[key], list), f"Key '{key}' is not a list, got {type(data[key])}"


@then(parsers.parse("l'offre avec id={job_id:d} a saved = {saved_val:d}"))
def then_job_saved_status(seeded_db, job_id, saved_val):
    """Verify a specific job has the expected saved status."""
    from tests.utils.db_helpers import get_job_by_id

    job = get_job_by_id(seeded_db, job_id)
    assert job is not None, f"Job with ID {job_id} not found"
    assert job["saved"] == saved_val, f"Expected saved={saved_val} for job {job_id}, got {job['saved']}"
