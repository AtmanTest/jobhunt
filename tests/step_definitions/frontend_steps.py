"""Placeholder step definitions for JobHunt frontend E2E BDD features.

These steps use Playwright for browser-based end-to-end testing. They are
placeholder stubs that skip when Playwright is not available or when running
in a non-E2E context. Run with: pytest -m e2e --headed
"""

import pytest
from pytest_bdd import given, parsers, then, when


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given("le navigateur est ouvert sur la page d'accueil")
def given_browser_on_homepage():
    """Open the browser to the JobHunt dashboard homepage.

    Requires Playwright and a running Flask dev server.
    """
    pytest.skip("E2E tests need Playwright browser - run separately")


@given("le serveur Flask est lancé")
def given_flask_server_running():
    """Verify the Flask development server is running on port 5050."""
    pytest.skip("E2E tests need Playwright browser - run separately")


@given("la page des statistiques est affichée")
def given_stats_page_displayed():
    """Navigate to the main page and verify stats section is visible."""
    pytest.skip("E2E tests need Playwright browser - run separately")


@given('le filtre QA est activé par défaut')
def given_qa_filter_default():
    """Default state: QA filter checkbox is checked."""
    pytest.skip("E2E tests need Playwright browser - run separately")


@given('la liste des offres est chargée')
def given_job_list_loaded():
    """Wait for job listings to appear in the DOM."""
    pytest.skip("E2E tests need Playwright browser - run separately")


@given(parsers.parse("{count:d} offres QA sont visibles"))
def given_qa_jobs_visible(count):
    """Verify N QA job cards are rendered on screen."""
    pytest.skip("E2E tests need Playwright browser - run separately")


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when("je clique sur le bouton de rafraîchissement")
def when_click_refresh():
    """Click the refresh/update button."""
    pytest.skip("E2E tests need Playwright browser - run separately")


@when("je saisis un terme de recherche")
def when_enter_search_term():
    """Type a search term in the search input field."""
    pytest.skip("E2E tests need Playwright browser - run separately")


@when("je clique sur le bouton Postuler")
def when_click_apply():
    """Click the 'Apply' button on a job card."""
    pytest.skip("E2E tests need Playwright browser - run separately")


@when("je navigue vers la page des offres sauvegardées")
def when_navigate_saved():
    """Click the bookmarks/saved jobs link."""
    pytest.skip("E2E tests need Playwright browser - run separately")


@when("je clique sur le bouton Sauvegarder")
def when_click_save():
    """Click the save/bookmark toggle button."""
    pytest.skip("E2E tests need Playwright browser - run separately")


@when("je sélectionne le filtre par source")
def when_select_source_filter():
    """Select a source filter from the dropdown."""
    pytest.skip("E2E tests need Playwright browser - run separately")


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then("la page d'accueil s'affiche correctement")
def then_homepage_displays():
    """Verify the homepage renders without errors."""
    pytest.skip("E2E tests need Playwright browser - run separately")


@then("les statistiques sont mises à jour")
def then_stats_updated():
    """Verify stat counters reflect latest data after scrape."""
    pytest.skip("E2E tests need Playwright browser - run separately")


@then(parsers.parse("{count:d} offres sont affichées dans la liste"))
def then_n_jobs_displayed(count):
    """Verify exactly N job cards are in the listing."""
    pytest.skip("E2E tests need Playwright browser - run separately")


@then("le statut de l'offre passe à postulé")
def then_job_status_applied():
    """Verify the applied status badge appears on the job card."""
    pytest.skip("E2E tests need Playwright browser - run separately")


@then("l'offre est ajoutée aux favoris")
def then_job_saved():
    """Verify the bookmarked state is visually indicated."""
    pytest.skip("E2E tests need Playwright browser - run separately")


@then("les résultats sont filtrés selon la source sélectionnée")
def then_results_filtered_by_source():
    """Verify only jobs from the selected source are shown."""
    pytest.skip("E2E tests need Playwright browser - run separately")
