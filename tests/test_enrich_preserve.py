"""Regression tests: AI enrichment must never wipe scraper-derived columns.

Bug: auto_enrich.update_job() wrote every extracted column unconditionally, so an
LLM answer of null/[]/"" overwrote deterministic values produced by scraper.py
(detect_remote_type / detect_contract_type) — ~500 jobs lost remote_type.
"""
import sqlite3

import pytest

import auto_enrich


COLUMNS = ("tech_stack", "seniority", "contract_type", "remote_type",
           "salary_min", "salary_max", "currency")


def _conn(values):
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE jobs (
            id TEXT PRIMARY KEY, tech_stack TEXT, seniority TEXT, contract_type TEXT,
            remote_type TEXT, salary_min INTEGER, salary_max INTEGER, currency TEXT,
            ai_enriched INTEGER DEFAULT 0
        )
    """)
    conn.execute(
        f"INSERT INTO jobs (id, {', '.join(COLUMNS)}, ai_enriched) VALUES (?,?,?,?,?,?,?,?,0)",
        ("j1", *values),
    )
    return conn


def _get(conn, col):
    return conn.execute(f"SELECT {col} FROM jobs WHERE id='j1'").fetchone()[0]


def test_null_llm_answer_does_not_wipe_scraper_values():
    conn = _conn(('["Pytest"]', None, "mission/freelance", "remote", 500, 600, "EUR"))
    auto_enrich.update_job("j1", {
        "tech_stack": [], "seniority": None, "contract_type": None, "remote_type": None,
        "salary_min": None, "salary_max": None, "currency": None,
    }, conn)

    assert _get(conn, "tech_stack") == '["Pytest"]'
    assert _get(conn, "contract_type") == "mission/freelance"
    assert _get(conn, "remote_type") == "remote"
    assert _get(conn, "salary_min") == 500
    assert _get(conn, "salary_max") == 600
    assert _get(conn, "currency") == "EUR"
    assert _get(conn, "ai_enriched") == 1


def test_blank_strings_do_not_wipe():
    conn = _conn((None, None, "ambigüe", "hybrid", None, None, None))
    auto_enrich.update_job("j1", {
        "tech_stack": [], "seniority": " ", "contract_type": "", "remote_type": "  ",
        "salary_min": None, "salary_max": None, "currency": "",
    }, conn)

    assert _get(conn, "contract_type") == "ambigüe"
    assert _get(conn, "remote_type") == "hybrid"


def test_fills_empty_columns_and_normalizes_remote_vocabulary():
    conn = _conn((None, None, "", "", None, None, None))
    auto_enrich.update_job("j1", {
        "tech_stack": ["Playwright", " Cypress ", ""], "seniority": "senior",
        "contract_type": "fulltime", "remote_type": "fully_remote",
        "salary_min": 100, "salary_max": 150, "currency": "USD",
    }, conn)

    assert _get(conn, "tech_stack") == '["Playwright", "Cypress"]'
    assert _get(conn, "seniority") == "senior"
    assert _get(conn, "contract_type") == "fulltime"
    assert _get(conn, "remote_type") == "remote"  # alias -> site vocabulary
    assert _get(conn, "salary_min") == 100


def test_missing_keys_are_tolerated():
    conn = _conn(("[]", None, "ambigüe", "remote", None, None, None))
    auto_enrich.update_job("j1", {}, conn)

    assert _get(conn, "contract_type") == "ambigüe"
    assert _get(conn, "remote_type") == "remote"
    assert _get(conn, "ai_enriched") == 1
