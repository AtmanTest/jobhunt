"""Contrats de données — l'app et l'ingestion ne doivent pas casser leur schéma.

Garde-fou rapide (aucune dépendance réseau) : si la forme des offres change,
la CI casse ici avant d'atteindre le dashboard ou Supabase.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.api.contracts import assert_matches_schema
from tests.data.factories import job, offer

FIXTURES = Path(__file__).parent / "fixtures"
pytestmark = pytest.mark.api


@pytest.mark.contract
def test_factory_job_respects_contract():
    assert_matches_schema(job(), "job")


@pytest.mark.contract
def test_factory_offer_respects_contract():
    assert_matches_schema(offer(), "offer")


@pytest.mark.contract
def test_sample_fixture_respects_job_contract():
    rows = json.loads((FIXTURES / "sample_jobs.json").read_text(encoding="utf-8"))
    rows = rows if isinstance(rows, list) else rows.get("jobs", [])
    assert rows, "sample_jobs.json est vide"
    for row in rows:
        assert_matches_schema(row, "job")


@pytest.mark.contract
def test_contract_rejects_bad_url():
    with pytest.raises(AssertionError):
        assert_matches_schema(job(url="pas-une-url"), "job")


@pytest.mark.contract
def test_contract_rejects_missing_title():
    row = job()
    del row["title"]
    with pytest.raises(AssertionError):
        assert_matches_schema(row, "job")


@pytest.mark.contract
def test_seed_inserts_factory_rows(test_db):
    from tests.data.factories import seed

    assert seed(test_db, [job(title="QA Mobile"), job(title="QA Web")]) == 2
    n = test_db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    assert n == 2
