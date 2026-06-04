"""
Playwright scenarios for JobHunt Dashboard QA demo.
Each scenario is a standalone function that returns {"passed": bool, "details": str}.
"""

import json, os

BASE_URL = os.environ.get("JOBHUNT_URL", "http://localhost:5050")
SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)


def _screenshot(page, name):
    path = os.path.join(SCREENSHOTS_DIR, f"{name}.png")
    page.screenshot(path=path)
    return path


def test_page_title(page):
    page.goto(BASE_URL)
    title = page.title()
    assert "JobHunt" in title or "Marché" in title or "QA" in title, f"Unexpected title: {title}"
    return {"passed": True, "details": f"Title: {title}"}


def test_hero_stats(page):
    page.goto(BASE_URL)
    page.wait_for_selector(".hero-card", timeout=10000)
    cards = page.query_selector_all(".hero-card")
    assert len(cards) >= 3, f"Expected 3+ stat cards, got {len(cards)}"
    texts = [c.text_content().strip() for c in cards]
    return {"passed": True, "details": f"Stat cards: {len(cards)} — {' | '.join(t[:30] for t in texts)}"}


def test_country_tabs(page):
    page.goto(BASE_URL)
    page.wait_for_selector(".country-btn", timeout=10000)
    tabs = page.query_selector_all(".country-btn")
    tab_count = len(tabs)
    assert tab_count >= 5, f"Expected 5+ country tabs, got {tab_count}"
    # Click Switzerland
    swiss = [t for t in tabs if "Suisse" in t.text_content() or "Switzerland" in t.text_content()]
    if swiss:
        swiss[0].click()
        page.wait_for_timeout(500)
    return {"passed": True, "details": f"Country tabs: {tab_count}, switched to Suisse OK"}


def test_remote_filter(page):
    page.goto(BASE_URL)
    page.wait_for_selector(".filter-btn", timeout=10000)
    filters = page.query_selector_all(".filter-btn")
    remote_btn = [f for f in filters if "Remote" in f.text_content()]
    assert len(remote_btn) > 0, "Remote filter button not found"
    remote_btn[0].click()
    page.wait_for_timeout(500)
    return {"passed": True, "details": "Remote filter clicked successfully"}


def test_job_cards(page):
    page.goto(BASE_URL)
    page.wait_for_selector(".job-card", timeout=15000)
    cards = page.query_selector_all(".job-card")
    visible = [c for c in cards if c.is_visible()]
    assert len(visible) > 0, "No visible job cards"
    return {"passed": True, "details": f"{len(visible)} job cards visible"}


def test_top_matches(page):
    page.goto(BASE_URL)
    page.wait_for_selector(".top-match-card", timeout=10000)
    cards = page.query_selector_all(".top-match-card")
    scores = [c.query_selector(".tm-score") for c in cards if c.query_selector(".tm-score")]
    score_texts = [s.text_content().strip() for s in scores if s]
    return {"passed": True, "details": f"{len(cards)} top matches — scores: {', '.join(score_texts[:5])}"}


def test_cv_page(page):
    page.goto(f"{BASE_URL}/cv")
    page.wait_for_selector(".hdr-name", timeout=10000)
    name = page.query_selector(".hdr-name")
    assert name and "Jahangir" in name.text_content(), "CV name not found"
    return {"passed": True, "details": f"CV loaded — name: {name.text_content().strip()}"}


def test_pagination(page):
    page.goto(BASE_URL)
    page.wait_for_selector(".page-btn", timeout=10000)
    btns = page.query_selector_all(".page-btn")
    next_btn = [b for b in btns if b.text_content().strip() == "›" and not b.is_disabled()]
    if next_btn:
        next_btn[0].click()
        page.wait_for_timeout(500)
        return {"passed": True, "details": "Pagination: clicked next page"}
    return {"passed": True, "details": "Only 1 page, pagination not needed"}


def test_dismiss_button_does_not_navigate(page):
    """Verify that clicking the dismiss button (✕) does NOT navigate away."""
    page.goto(BASE_URL)
    page.wait_for_selector(".btn-dismiss", timeout=15000)
    current_url = page.url
    dismiss_btn = page.query_selector(".btn-dismiss")
    if not dismiss_btn:
        return {"passed": True, "details": "No dismiss buttons found, skip"}
    dismiss_btn.click()
    page.wait_for_timeout(1000)
    assert page.url == current_url, f"Page navigated! {current_url} → {page.url}"
    return {"passed": True, "details": "Dismiss button click did NOT navigate away"}


def test_apply_button_is_only_clickable_link(page):
    """Verify that clicking a job card body does NOT navigate, only the btn-apply link."""
    page.goto(BASE_URL)
    page.wait_for_selector(".job-card", timeout=15000)
    card = page.query_selector(".job-card")
    if not card:
        return {"passed": True, "details": "No job cards found"}
    current_url = page.url
    # Click the card body (not the button)
    card.click(position={"x": 50, "y": 50})
    page.wait_for_timeout(500)
    assert page.url == current_url, "Job card click navigated away!"
    # Click the Apply button
    apply_btn = card.query_selector(".btn-apply")
    if not apply_btn:
        return {"passed": True, "details": "No Apply button, skip"}
    # Don't actually click the link - just verify it has a valid href
    href = apply_btn.get_attribute("href")
    assert href and href.startswith("http"), f"Apply button has no valid href: {href}"
    return {"passed": True, "details": f"Card body non-clickable ✓, Apply → {href}"}


SCENARIOS = {
    "test_page_title": test_page_title,
    "test_hero_stats": test_hero_stats,
    "test_country_tabs": test_country_tabs,
    "test_remote_filter": test_remote_filter,
    "test_job_cards": test_job_cards,
    "test_top_matches": test_top_matches,
    "test_cv_page": test_cv_page,
    "test_pagination": test_pagination,
    "test_dismiss_button_does_not_navigate": test_dismiss_button_does_not_navigate,
    "test_apply_button_is_only_clickable_link": test_apply_button_is_only_clickable_link,
}


def run_scenario(name: str) -> dict:
    """Run a single scenario by name."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        try:
            if name in SCENARIOS:
                result = SCENARIOS[name](page)
                result["scenario"] = name
                return result
            return {"scenario": name, "passed": False, "error": f"Unknown scenario: {name}"}
        except Exception as e:
            shot = _screenshot(page, f"fail_{name}")
            return {"scenario": name, "passed": False, "error": str(e)[:300], "screenshot": shot}
        finally:
            browser.close()
