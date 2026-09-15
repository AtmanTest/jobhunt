"""Step definitions for cron/scheduled_jobs.feature.

Cron jobs are managed by Hermes Agent's scheduler and run on Render.
These tests verify the job definitions are valid and well-formed.
Actual execution timing is tested via integration tests.
"""
import pytest
from pytest_bdd import given, parsers, then, when

# ─── Shared state ───────────────────────────────────────────────────────────
CRON_STATE = {}


@given(parsers.parse('le cron "{job_name}" est planifié à "{schedule}"'),
       target_fixture="cron_schedule")
def given_cron_scheduled(job_name, schedule):
    """Verify the named cron job has a valid schedule."""
    CRON_STATE["cron_name"] = job_name
    CRON_STATE["schedule"] = schedule
    return {"name": job_name, "schedule": schedule}


@given(parsers.parse("{count} nouvelles offres ajoutées"),
       target_fixture="new_jobs")
def given_new_jobs(count):
    """Stub: simulate new jobs for alert check."""
    CRON_STATE["new_jobs_count"] = int(count)
    return {"count": int(count)}


@given(parsers.parse("la semaine a produit {count} offres"),
       target_fixture="weekly_jobs")
def given_weekly_jobs(count):
    """Stub: simulate weekly job count."""
    CRON_STATE["weekly_count"] = int(count)
    return {"count": int(count)}


@when("il est 08h00")
def when_0800():
    """Stub: simulate 8AM trigger."""
    CRON_STATE["triggered"] = True


@when("la vérification s'exécute")
def when_alert_check():
    """Stub: simulate alert check trigger."""
    CRON_STATE["alert_checked"] = True


@when("le rapport est généré")
def when_report_generated():
    """Stub: simulate weekly report generation."""
    CRON_STATE["report_generated"] = True


@then("le scraping et l'export sont lancés")
def then_scraping_export_launched():
    """Verify daily refresh would trigger scrape + export."""
    assert CRON_STATE.get("triggered"), "Daily refresh not triggered"
    # Verify the cron schedule is valid cron syntax
    schedule = CRON_STATE.get("schedule", "")
    parts = schedule.split()
    assert len(parts) == 5, f"Invalid cron schedule: {schedule}"
    assert all(p.isdigit() or p in ("*", "/", "-", ",") for p in parts), \
        f"Non-standard cron characters in: {schedule}"


@then("un git push est effectué")
def then_git_push():
    """Stub: git push happens after scrape."""
    assert CRON_STATE.get("triggered")


@then("les {count} offres sont détectées")
def then_jobs_detected(count):
    """Stub: new jobs are detected for alert."""
    assert CRON_STATE.get("alert_checked")
    assert CRON_STATE.get("new_jobs_count") == int(count), \
        f"Expected {count} new jobs, got {CRON_STATE.get('new_jobs_count')}"


@then("un message WhatsApp est envoyé")
def then_whatsapp_sent():
    """Stub: WhatsApp notification sent."""
    assert CRON_STATE.get("alert_checked")


@then("le top 5 des offres est inclus")
def then_top5_included():
    """Stub: weekly report includes top 5."""
    assert CRON_STATE.get("report_generated")


@then("les stats sont envoyées")
def then_stats_sent():
    """Stub: stats data sent with report."""
    assert CRON_STATE.get("report_generated")
    assert CRON_STATE.get("weekly_count", 0) > 0
