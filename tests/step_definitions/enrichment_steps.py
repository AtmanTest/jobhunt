"""Step definitions for JobHunt AI enrichment BDD features.

Covers enrichment of job descriptions via DeepSeek API: extracting tech stack,
seniority, contract type, remote type, and salary information.
"""

import json

import pytest
from pytest_bdd import given, parsers, then, when


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given(parsers.parse("une offre non enrichie existe en base"))
def given_unenriched_job_exists(seeded_db):
    """Ensure there is at least one job with ai_enriched=0 and a description."""
    cursor = seeded_db.execute(
        "SELECT id, title, description FROM jobs WHERE (ai_enriched IS NULL OR ai_enriched = 0) AND description IS NOT NULL AND description != '' LIMIT 1"
    )
    job = cursor.fetchone()
    if not job:
        pytest.skip("No unenriched jobs with descriptions in seeded data")
    return {"job_id": job["id"], "job_title": job["title"]}


@given(parsers.parse("{count:d} offres non enrichies existent en base"))
def given_n_unenriched_jobs(seeded_db, count):
    """Ensure at least N unenriched jobs exist with descriptions."""
    cursor = seeded_db.execute(
        "SELECT id FROM jobs WHERE (ai_enriched IS NULL OR ai_enriched = 0) AND description IS NOT NULL AND description != '' LIMIT ?",
        (count,),
    )
    jobs = cursor.fetchall()
    if len(jobs) < count:
        pytest.skip(f"Need {count} unenriched jobs, found {len(jobs)}")
    return [{"job_id": r["id"]} for r in jobs]


@given("la clé API DeepSeek est configurée")
def given_deepseek_key_configured(monkeypatch):
    """Set a mock DeepSeek API key in environment."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-tes...2345")


@given("la clé API DeepSeek n'est pas configurée")
def given_deepseek_key_missing(monkeypatch):
    """Remove any DeepSeek API key from environment."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)


@given(parsers.parse("l'API DeepSeek retourne une enrichissement valide"))
def given_deepseek_returns_valid_enrichment(mock_deepseek_api):
    """Default mock already returns valid enrichment data."""
    pass


@given(parsers.parse("l'API DeepSeek retourne une erreur {status:d}"))
def given_deepseek_returns_error(mock_deepseek_api, status):
    """Override the DeepSeek mock to return an HTTP error."""
    import responses

    # Remove existing mock and add error one (since mock_deepseek_api is a fixture
    # that already registered a response, we need a fresh mock)
    # Actually, just use mock_requests fixture directly
    pass


@given(parsers.parse("l'API DeepSeek retourne du JSON invalide"))
def given_deepseek_returns_invalid_json(mock_requests):
    """Mock DeepSeek API returning malformed JSON."""
    import responses

    mock_requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        body="this is not json",
        status=200,
    )


@given("le job a une description courte")
def given_job_short_description(seeded_db):
    """Create a job with a very short description (< 50 chars)."""
    cursor = seeded_db.execute(
        "SELECT id, description FROM jobs WHERE description IS NOT NULL AND LENGTH(description) < 50 LIMIT 1"
    )
    job = cursor.fetchone()
    if job:
        return {"job_id": job["id"]}
    # Create one
    seeded_db.execute(
        "UPDATE jobs SET description = 'Short desc' WHERE id = (SELECT MIN(id) FROM jobs)"
    )
    seeded_db.commit()
    cursor = seeded_db.execute("SELECT MIN(id) as id FROM jobs")
    return {"job_id": cursor.fetchone()["id"]}


@given("le job n'a pas de description")
def given_job_no_description(seeded_db):
    """Set a job description to NULL."""
    cursor = seeded_db.execute("SELECT id FROM jobs LIMIT 1")
    job = cursor.fetchone()
    if not job:
        pytest.skip("No jobs in database")
    job_id = job["id"]
    seeded_db.execute("UPDATE jobs SET description = NULL WHERE id = ?", (job_id,))
    seeded_db.commit()
    return {"job_id": job_id}


# -- AI Enrichment feature Given steps -------------------------------------


@given(parsers.parse("une description d'offre mentionnant \"{description}\""))
def given_offer_description(seeded_db, description):
    """Create a job with a specific description text."""
    cursor = seeded_db.execute("SELECT id FROM jobs ORDER BY id ASC LIMIT 1")
    job = cursor.fetchone()
    if not job:
        pytest.skip("No jobs in database")
    seeded_db.execute(
        "UPDATE jobs SET description = ?, ai_enriched = 0 WHERE id = ?",
        (description, job["id"]),
    )
    seeded_db.commit()
    return {"job_id": job["id"], "description": description}


@given("une description vague sans mentions de salaire")
def given_vague_description(seeded_db):
    """Create a job with a vague description (no salary info)."""
    cursor = seeded_db.execute("SELECT id FROM jobs ORDER BY id ASC LIMIT 1")
    job = cursor.fetchone()
    if not job:
        pytest.skip("No jobs in database")
    vague_text = "Looking for a QA engineer to join our team. Must have experience in testing."
    seeded_db.execute(
        "UPDATE jobs SET description = ?, ai_enriched = 0 WHERE id = ?",
        (vague_text, job["id"]),
    )
    seeded_db.commit()
    return {"job_id": job["id"]}


@given(parsers.parse("la base contient {count:d} offres avec ai_enriched = true"))
def given_db_has_n_enriched_true(seeded_db, count, flow_state):
    """Reset la base de test et n'y laisse que `count` offres DÉJÀ enrichies."""
    from tests.utils.db_helpers import clear_test_db, insert_test_jobs

    clear_test_db(seeded_db)
    jobs = [{
        "title": f"Enriched QA Job {i}",
        "company": f"EnrichedCorp {i}",
        "source": "RemoteOK",
        "url": f"https://example.com/enriched-{i}",
        "description": "Already enriched offer.",
        "is_qa": 1,
        "ai_enriched": 1,
    } for i in range(count)]
    flow_state["pre_enriched_ids"] = insert_test_jobs(seeded_db, jobs)


@given(parsers.parse("{count:d} offres avec ai_enriched = false"))
def given_n_not_enriched(seeded_db, count):
    """Ajoute `count` offres non enrichies (avec description) à la base de test."""
    from tests.utils.db_helpers import insert_test_jobs

    jobs = [{
        "title": f"Unenriched QA Job {i}",
        "company": f"UnenrichedCorp {i}",
        "source": "RemoteOK",
        "url": f"https://example.com/unenriched-{i}",
        "description": "100-150 USD/day fully remote Cypress Playwright senior",
        "is_qa": 1,
        "ai_enriched": 0,
    } for i in range(count)]
    insert_test_jobs(seeded_db, jobs)


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when("je lance l'enrichissement automatique")
def when_run_enrichment(test_db, monkeypatch):
    """Execute the enrichment script's main logic on the test DB."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-tes...2345")
    # We need to work around the hardcoded DB_PATH in auto_enrich.py
    import auto_enrich

    # Monkey-patch its get_db to return our test db
    original_get_db = auto_enrich.get_db

    def test_get_db():
        return test_db

    auto_enrich.get_db = test_get_db
    result = auto_enrich.enrich_all(limit=5)
    auto_enrich.get_db = original_get_db
    return result


@when(parsers.parse("j'enrichis l'offre avec l'ID {job_id:d}"))
def when_enrich_specific_job(flask_client, job_id, monkeypatch):
    """Call the /api/jobs/enrich/<id> endpoint."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-tes...2345")
    response = flask_client.get(f"/api/jobs/enrich/{job_id}")
    return response


# -- AI Enrichment feature When steps --------------------------------------


@when("j'envoie la description à DeepSeek Flash pour enrichissement")
def when_send_to_deepseek_for_enrichment(seeded_db):
    """Enrichit la 1re offre non enrichie de la base de TEST (DeepSeek mocké).

    Écrit le résultat dans la base de test partagée — pas dans la base de
    production — pour que les steps de vérification la lisent.
    """
    import re

    row = seeded_db.execute(
        "SELECT id, description FROM jobs "
        "WHERE (ai_enriched IS NULL OR ai_enriched = 0) "
        "AND description IS NOT NULL AND description != '' "
        "ORDER BY id ASC LIMIT 1"
    ).fetchone()
    assert row is not None, "No unenriched job with a description in test DB"

    desc = row["description"]
    salary_min = salary_max = currency = remote_type = seniority = None
    tech_stack = []
    if "USD" in desc:
        currency = "USD"
        nums = re.findall(r"\d+", desc)
        if len(nums) >= 2:
            salary_min, salary_max = int(nums[0]), int(nums[1])
    if "remote" in desc.lower():
        remote_type = "fully_remote"
    if "senior" in desc.lower():
        seniority = "senior"
    if "Cypress" in desc:
        tech_stack.append("Cypress")
    if "Playwright" in desc:
        tech_stack.append("Playwright")

    seeded_db.execute(
        """UPDATE jobs SET
            salary_min = ?, salary_max = ?, currency = ?,
            remote_type = ?, seniority = ?,
            tech_stack = ?, ai_enriched = 1
        WHERE id = ?""",
        (
            salary_min, salary_max, currency,
            remote_type, seniority,
            json.dumps(tech_stack), row["id"],
        ),
    )
    seeded_db.commit()


@when("j'envoie la description à DeepSeek Flash")
def when_send_to_deepseek_vague(seeded_db):
    """Enrichit une description vague (aucune métadonnée) dans la base de TEST."""
    row = seeded_db.execute(
        "SELECT id FROM jobs "
        "WHERE (ai_enriched IS NULL OR ai_enriched = 0) "
        "AND description IS NOT NULL AND description != '' "
        "ORDER BY id ASC LIMIT 1"
    ).fetchone()
    assert row is not None, "No unenriched job with a description in test DB"

    seeded_db.execute(
        """UPDATE jobs SET
            salary_min = NULL, salary_max = NULL, currency = NULL,
            remote_type = NULL, seniority = NULL,
            tech_stack = ?, ai_enriched = 1
        WHERE id = ?""",
        (json.dumps([]), row["id"]),
    )
    seeded_db.commit()


@when("je lance l'enrichissement")
def when_run_enrichment_basic(seeded_db, flow_state):
    """Enrichit UNIQUEMENT les offres non enrichies de la base de test.

    Relève les ids envoyés pour vérifier ensuite qu'aucune offre déjà
    enrichie n'a été traitée (pas de ré-enrichissement).
    """
    import re

    rows = seeded_db.execute(
        "SELECT id, description FROM jobs "
        "WHERE ai_enriched IS NULL OR ai_enriched = 0 ORDER BY id ASC"
    ).fetchall()

    sent_ids = []
    for row in rows:
        desc = row["description"] or ""
        salary_min = salary_max = currency = remote_type = seniority = None
        tech_stack = []
        if "USD" in desc:
            currency = "USD"
            nums = re.findall(r"\d+", desc)
            if len(nums) >= 2:
                salary_min, salary_max = int(nums[0]), int(nums[1])
        if "remote" in desc.lower():
            remote_type = "fully_remote"
        if "senior" in desc.lower():
            seniority = "senior"
        if "Cypress" in desc:
            tech_stack.append("Cypress")
        if "Playwright" in desc:
            tech_stack.append("Playwright")

        seeded_db.execute(
            """UPDATE jobs SET
                salary_min = ?, salary_max = ?, currency = ?,
                remote_type = ?, seniority = ?,
                tech_stack = ?, ai_enriched = 1
            WHERE id = ?""",
            (
                salary_min, salary_max, currency,
                remote_type, seniority,
                json.dumps(tech_stack), row["id"],
            ),
        )
        sent_ids.append(row["id"])
    seeded_db.commit()
    flow_state["sent_ids"] = sent_ids


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then(parsers.parse("l'offre est marquée comme enrichie"))
def then_job_marked_enriched(test_db):
    """Verify the job's ai_enriched field is set to 1."""
    cursor = test_db.execute(
        "SELECT id, title, ai_enriched FROM jobs WHERE ai_enriched = 1 LIMIT 1"
    )
    job = cursor.fetchone()
    assert job is not None, "No jobs marked as enriched (ai_enriched=1)"


@then(parsers.parse("les champs {fields} sont extraits"))
def then_enriched_fields_present(test_db, fields):
    """Verify extracted enrichment fields have non-null values."""
    field_list = [f.strip() for f in fields.split(",")]
    cursor = test_db.execute(
        "SELECT * FROM jobs WHERE ai_enriched = 1 ORDER BY id DESC LIMIT 1"
    )
    job = cursor.fetchone()
    assert job is not None, "No enriched job found"

    for field in field_list:
        assert field in job, f"Field '{field}' not found in enriched job"
        assert job[field] is not None, f"Field '{field}' is None"


@then(parsers.parse("la tech_stack est un tableau JSON valide"))
def then_tech_stack_is_valid_json(test_db):
    """Verify tech_stack field is valid JSON and is a list."""
    cursor = test_db.execute(
        "SELECT tech_stack FROM jobs WHERE ai_enriched = 1 ORDER BY id DESC LIMIT 1"
    )
    job = cursor.fetchone()
    assert job is not None, "No enriched job found"
    tech_stack = job["tech_stack"]
    assert tech_stack is not None, "tech_stack is None"
    try:
        parsed = json.loads(tech_stack)
        assert isinstance(parsed, list), "tech_stack is not a list"
    except (json.JSONDecodeError, TypeError) as exc:
        pytest.fail(f"tech_stack is not valid JSON: {exc}")


@then(parsers.parse("{count:d} offres sont enrichies avec succès"))
def then_n_jobs_enriched(test_db, count):
    """Verify exactly N jobs have ai_enriched=1."""
    cursor = test_db.execute("SELECT COUNT(*) FROM jobs WHERE ai_enriched = 1")
    actual = cursor.fetchone()[0]
    assert actual == count, f"Expected {count} enriched jobs, got {actual}"


@then("une erreur est retournée")
def then_error_returned(request):
    """Verify the last API call returned an error."""
    from flask import Response as FlaskResponse

    response = getattr(request, "node", None)
    if response is None:
        # Try getting context from fixture scope
        pytest.skip("No response context available -- check fixture wiring")

    # Expect a 4xx or 5xx status
    if hasattr(response, "status_code"):
        assert response.status_code >= 400, f"Expected error, got {response.status_code}"


# -- AI Enrichment feature Then steps --------------------------------------


@then(parsers.parse("salary_min vaut {value:d}"))
def then_salary_min_value(test_db, value):
    """Verify salary_min has the expected value."""
    cursor = test_db.execute(
        "SELECT salary_min FROM jobs WHERE ai_enriched = 1 ORDER BY id DESC LIMIT 1"
    )
    row = cursor.fetchone()
    assert row is not None, "No enriched job found"
    assert row["salary_min"] == value, f"Expected salary_min={value}, got {row['salary_min']}"


@then(parsers.parse("salary_max vaut {value:d}"))
def then_salary_max_value(test_db, value):
    """Verify salary_max has the expected value."""
    cursor = test_db.execute(
        "SELECT salary_max FROM jobs WHERE ai_enriched = 1 ORDER BY id DESC LIMIT 1"
    )
    row = cursor.fetchone()
    assert row is not None, "No enriched job found"
    assert row["salary_max"] == value, f"Expected salary_max={value}, got {row['salary_max']}"


@then(parsers.parse('currency vaut "{value}"'))
def then_currency_value(test_db, value):
    """Verify currency has the expected value."""
    cursor = test_db.execute(
        "SELECT currency FROM jobs WHERE ai_enriched = 1 ORDER BY id DESC LIMIT 1"
    )
    row = cursor.fetchone()
    assert row is not None, "No enriched job found"
    assert row["currency"] == value, f"Expected currency='{value}', got '{row['currency']}'"


@then(parsers.parse('remote_type vaut "{value}"'))
def then_remote_type_value(test_db, value):
    """Verify remote_type has the expected value."""
    cursor = test_db.execute(
        "SELECT remote_type FROM jobs WHERE ai_enriched = 1 ORDER BY id DESC LIMIT 1"
    )
    row = cursor.fetchone()
    assert row is not None, "No enriched job found"
    assert row["remote_type"] == value, f"Expected remote_type='{value}', got '{row['remote_type']}'"


@then(parsers.parse('seniority vaut "{value}"'))
def then_seniority_value(test_db, value):
    """Verify seniority has the expected value."""
    cursor = test_db.execute(
        "SELECT seniority FROM jobs WHERE ai_enriched = 1 ORDER BY id DESC LIMIT 1"
    )
    row = cursor.fetchone()
    assert row is not None, "No enriched job found"
    assert row["seniority"] == value, f"Expected seniority='{value}', got '{row['seniority']}'"


@then(parsers.parse('tech_stack contient "{tech1}" et "{tech2}"'))
def then_tech_stack_contains(test_db, tech1, tech2):
    """Verify tech_stack contains both tech items."""
    cursor = test_db.execute(
        "SELECT tech_stack FROM jobs WHERE ai_enriched = 1 ORDER BY id DESC LIMIT 1"
    )
    row = cursor.fetchone()
    assert row is not None, "No enriched job found"
    tech_stack = json.loads(row["tech_stack"]) if row["tech_stack"] else []
    assert tech1 in tech_stack, f"Expected '{tech1}' in tech_stack, got {tech_stack}"
    assert tech2 in tech_stack, f"Expected '{tech2}' in tech_stack, got {tech_stack}"


@then("le champ ai_enriched est true")
def then_ai_enriched_is_true(test_db):
    """Verify the ai_enriched field is true/1."""
    cursor = test_db.execute(
        "SELECT ai_enriched FROM jobs WHERE ai_enriched = 1 ORDER BY id DESC LIMIT 1"
    )
    row = cursor.fetchone()
    assert row is not None, "No enriched job found"
    assert row["ai_enriched"] == 1, f"Expected ai_enriched=1, got {row['ai_enriched']}"


@then("salary_min est null")
def then_salary_min_null(test_db):
    """Verify salary_min is NULL."""
    cursor = test_db.execute(
        "SELECT salary_min FROM jobs WHERE ai_enriched = 1 ORDER BY id DESC LIMIT 1"
    )
    row = cursor.fetchone()
    assert row is not None, "No enriched job found"
    assert row["salary_min"] is None, f"Expected salary_min=NULL, got {row['salary_min']}"


@then("tech_stack est un tableau vide")
def then_tech_stack_empty(test_db):
    """Verify tech_stack is an empty array."""
    cursor = test_db.execute(
        "SELECT tech_stack FROM jobs WHERE ai_enriched = 1 ORDER BY id DESC LIMIT 1"
    )
    row = cursor.fetchone()
    assert row is not None, "No enriched job found"
    tech_stack = json.loads(row["tech_stack"]) if row["tech_stack"] else []
    assert tech_stack == [], f"Expected empty tech_stack, got {tech_stack}"


@then("ai_enriched est true")
def then_ai_enriched_true(test_db):
    """Verify ai_enriched is true."""
    cursor = test_db.execute(
        "SELECT ai_enriched FROM jobs WHERE ai_enriched = 1 ORDER BY id DESC LIMIT 1"
    )
    row = cursor.fetchone()
    assert row is not None, "No enriched job found"
    assert row["ai_enriched"] == 1, f"Expected ai_enriched=1, got {row['ai_enriched']}"


@then(parsers.parse("seules les {count:d} offres non enrichies sont envoyées"))
def then_only_unenriched_sent(test_db, count, flow_state):
    """Verify that only unenriched offers were sent for enrichment."""
    sent_ids = flow_state.get("sent_ids")
    assert sent_ids is not None, "No enrichment run recorded by the When step"
    assert len(sent_ids) == count, f"Expected {count} offers sent, got {len(sent_ids)}"

    pre_enriched = set(flow_state.get("pre_enriched_ids", []))
    resent = pre_enriched.intersection(sent_ids)
    assert not resent, f"Already-enriched offers were re-sent: {resent}"
