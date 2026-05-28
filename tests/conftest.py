"""Main pytest configuration and fixtures for JobHunt test suite."""

import json
import os
import sqlite3
import sys

import pytest
import responses

# Ensure app module is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Re-export API client for convenience
from tests.utils.api_client import APIClient  # noqa: E402, F401
from tests.utils.db_helpers import create_schema, clear_test_db  # noqa: E402, F401

# Register BDD step definition modules as pytest plugins so their fixtures are discovered
pytest_plugins = [
    "tests.step_definitions.scraping_steps",
    "tests.step_definitions.filtering_steps",
    "tests.step_definitions.enrichment_steps",
    "tests.step_definitions.api_steps",
    "tests.step_definitions.frontend_steps",
    "tests.step_definitions.regression_steps",
]

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def test_db():
    """Create an isolated SQLite test database with production-matching schema.

    Uses an in-memory database for speed. Yields the connection; drops all
    tables on teardown so each test gets a clean slate.

    Yields:
        sqlite3.Connection with row_factory set to sqlite3.Row
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def test_db_path(tmp_path):
    """Create an isolated file-based SQLite test database.

    Useful for testing code that requires a file path. Schema matches production.

    Yields:
        Path to the temporary database file
    """
    db_path = str(tmp_path / "test_jobs.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    conn.close()
    yield db_path


@pytest.fixture
def flask_app(test_db):
    """Create a Flask app instance configured to use the test database.

    Monkey-patches the app's DB_PATH and get_db() to use the in-memory test DB.

    Yields:
        Flask application instance
    """
    import app as app_module

    original_get_db = app_module.get_db

    def test_get_db():
        return test_db

    app_module.get_db = test_get_db
    app_module.DB_PATH = ":memory:"

    yield app_module.app

    app_module.get_db = original_get_db


@pytest.fixture
def flask_client(flask_app):
    """Create a Flask test client from the test-configured app.

    Yields:
        Flask test_client instance
    """
    with flask_app.test_client() as client:
        yield client


@pytest.fixture
def api_client(flask_client):
    """Create an APIClient wrapper around the Flask test client.

    Yields:
        APIClient instance
    """
    return APIClient(flask_client)


@pytest.fixture
def sample_jobs():
    """Load sample_jobs.json from fixtures directory.

    Returns:
        List of job dicts
    """
    path = os.path.join(FIXTURES_DIR, "sample_jobs.json")
    with open(path) as f:
        return json.load(f)


@pytest.fixture
def mock_remoteok_response():
    """Load mock_remoteok_response.json from fixtures directory.

    This simulates the JSON array returned by the RemoteOK API endpoint.
    First item is a meta/ad placeholder (which the scraper skips).

    Returns:
        List of job dicts as returned by the RemoteOK API
    """
    path = os.path.join(FIXTURES_DIR, "mock_remoteok_response.json")
    with open(path) as f:
        return json.load(f)


@pytest.fixture
def mock_requests():
    """Enable requests mocking via the responses library.

    Usage:
        mock_requests.get("https://remoteok.com/api", json=mock_data)

    Yields:
        responses.RequestsMock instance for registering mock endpoints
    """
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        yield rsps


@pytest.fixture
def mock_deepseek_api():
    """Mock the DeepSeek API endpoint used by enrichment.

    Uses the responses library to intercept POST requests to
    https://api.deepseek.com/v1/chat/completions.

    Returns a default successful response. Override with parametrize or
    by modifying the fixture return in individual tests.

    Yields:
        responses.RequestsMock instance with the DeepSeek endpoint pre-registered
    """
    default_response = {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "deepseek-chat",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "tech_stack": ["Cypress", "Playwright", "Python"],
                            "seniority": "mid",
                            "contract_type": "fulltime",
                            "remote_type": "fully_remote",
                            "salary_min": 80000,
                            "salary_max": 120000,
                            "currency": "USD",
                        }
                    ),
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 150, "completion_tokens": 50, "total_tokens": 200},
    }

    with responses.RequestsMock() as rsps:
        rsps.post(
            "https://api.deepseek.com/v1/chat/completions",
            json=default_response,
            status=200,
        )
        yield rsps


@pytest.fixture
def seeded_db(test_db, sample_jobs):
    """Create a test database pre-populated with sample jobs.

    Inserts all jobs from sample_jobs.json into the test_db.

    Yields:
        sqlite3.Connection with sample data
    """
    from tests.utils.db_helpers import insert_test_jobs

    insert_test_jobs(test_db, sample_jobs)
    yield test_db


@pytest.fixture
def empty_db(test_db):
    """Create a test database with no data (explicitly cleared).

    Yields:
        sqlite3.Connection with empty tables
    """
    clear_test_db(test_db)
    yield test_db


@pytest.fixture
def api_response():
    """Simple dict to store the last API response between BDD steps.

    Used by api_steps.py and other step definitions that need to share
    API call results across When and Then steps.
    """
    return {}


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "e2e: End-to-end tests requiring Playwright browser")
    config.addinivalue_line("markers", "slow: Tests that take longer than usual")
    config.addinivalue_line("markers", "scraping: Tests related to job scraper functionality")
    config.addinivalue_line("markers", "filtering: Tests related to job filtering")
    config.addinivalue_line("markers", "enrichment: Tests related to AI enrichment")
    config.addinivalue_line("markers", "api: Tests for API endpoints")
    config.addinivalue_line("markers", "regression: Regression and bug-fix tests")
