"""Jeu de données canonique pour les scénarios frontend E2E.

Ce module est la source unique de vérité pour la base servie par le serveur
E2E des scénarios BDD `tests/features/frontend/*.feature`.

Deux groupes d'offres sont créés :

* 18 « offres d'affichage » localisées en France, publiées côté freelance
  (``freelance_status = 'VALIDÉE'``) : ce sont elles que le dashboard
  affiche dans les onglets pays et « Tous ». Parmi elles, exactement 3 ont
  moins de 7 jours (badge NEW vert), 6 contiennent « Cypress » (recherche),
  8 sont « senior », 9 sont « freelance », 5 sont senior ET freelance.
* 5 « candidatures » hors périmètre pays (localisation ``Remote``) portant
  chacune un ``pipeline_stage`` distinct (new/applied/interview/offer/
  rejected) et un ``applied_at`` : elles alimentent la vue Kanban.
"""

from __future__ import annotations

import datetime as _dt
import os
import sqlite3
import time

# (title, company, days_ago, seniority, contract_type, tags, salary)
DISPLAY_JOBS = [
    ("QA Automation Engineer Cypress", "Acme", 1, "senior", "freelance", "QA, Cypress, Playwright", "600 EUR"),
    ("Senior QA Cypress Lead", "Globex", 3, "senior", "freelance", "Cypress, E2E, API", "650 EUR"),
    ("Test Automation Engineer Cypress", "Initech", 6, "mid", "freelance", "Cypress, JavaScript", "500 EUR"),
    ("QA Engineer", "TechCorp", 20, "mid", "cdi", "QA, Selenium", "45000 EUR"),
    ("Senior SDET", "Umbrella", 40, "senior", "cdi", "Playwright, Java", "70000 EUR"),
    ("QA Consultant Freelance", "Soyuz", 15, "senior", "freelance", "Testing, API", "550 EUR"),
    ("Junior QA Tester", "Hooli", 10, "junior", "cdi", "Manual, QA", "32000 EUR"),
    ("Senior Test Lead", "Pied Piper", 30, "senior", "freelance", "Cypress, CI/CD", "680 EUR"),
    ("QA Analyst", "Vandelay", 8, "mid", "cdi", "SQL, QA", "42000 EUR"),
    ("SDET Playwright", "Wonka", 9, "senior", "cdi", "Playwright, Python", "75000 EUR"),
    ("QA Automation Freelance", "Stark", 25, "mid", "freelance", "Selenium, Python", "520 EUR"),
    ("Test Engineer", "Wayne", 12, "junior", "freelance", "Manual, QA", "380 EUR"),
    ("Senior QA Architect", "Cyberdyne", 45, "senior", "cdi", "Strategy, QA", "85000 EUR"),
    ("QA Lead Cypress", "Soylent", 60, "senior", "freelance", "Cypress, Team", "700 EUR"),
    ("Automation QA", "Massive", 35, "mid", "cdi", "JavaScript, QA", "48000 EUR"),
    ("QA Engineer API", "Aperture", 18, "mid", "freelance", "API, Postman", "540 EUR"),
    ("Junior Automation Tester", "Black Mesa", 22, "junior", "cdi", "Cypress, JavaScript", "35000 EUR"),
    ("QA Specialist", "Oceanic", 50, "mid", "cdi", "QA, Regression", "44000 EUR"),
]

# (title, company, pipeline_stage)
KANBAN_JOBS = [
    ("Candidature A Postuler", "Alpha", "new"),
    ("Candidature Postulee", "Beta", "applied"),
    ("Candidature Entretien", "Gamma", "interview"),
    ("Candidature Offre", "Delta", "offer"),
    ("Candidature Refusee", "Epsilon", "rejected"),
]

_COLUMNS = (
    "title", "company", "source", "url", "location", "salary", "tags",
    "description", "date", "raw_date", "is_qa", "applied", "seniority",
    "contract_type", "remote_type", "freelance_status", "pipeline_stage",
    "applied_at", "viewed", "saved",
)


def _iso(days_ago: int) -> str:
    return (_dt.date.today() - _dt.timedelta(days=days_ago)).isoformat()


def _raw(days_ago: int) -> int:
    d = _dt.datetime.combine(_dt.date.today() - _dt.timedelta(days=days_ago), _dt.time())
    return int(time.mktime(d.timetuple()))


def _insert(conn, values):
    placeholders = ", ".join(["?"] * len(_COLUMNS))
    conn.execute(
        f"INSERT INTO jobs ({', '.join(_COLUMNS)}) VALUES ({placeholders})",
        values,
    )


def seed_database(db_path: str) -> dict:
    """(Re)crée le schéma et insère le jeu canonique. Idempotent.

    Returns:
        dict décrivant les ids attendus (recent, cypress, senior, freelance…).
    """
    import sys

    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if root not in sys.path:
        sys.path.insert(0, root)
    from tests.utils.db_helpers import create_schema  # noqa: E402

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    conn.execute("DELETE FROM jobs")
    conn.execute("DELETE FROM applications")
    conn.execute("DELETE FROM dismissed_jobs")

    recent_ids, cypress_ids, senior_ids, freelance_ids = [], [], [], []

    for idx, (title, company, days, seniority, contract, tags, salary) in enumerate(DISPLAY_JOBS, start=1):
        _insert(conn, (
            title, company, "RemoteOK", f"https://jobs.example.com/{idx}",
            "Paris, France", salary, tags,
            f"{title} — mission QA à Paris. Compétences : {tags}.",
            _iso(days), _raw(days), 1, 0, seniority, contract, "remote",
            "VALIDÉE", "new", None, 1, 0,
        ))
        row = conn.execute(
            "SELECT id FROM jobs WHERE url = ?", (f"https://jobs.example.com/{idx}",)
        ).fetchone()
        jid = row["id"]
        if days < 7:
            recent_ids.append(jid)
        if "cypress" in (title + " " + tags).lower():
            cypress_ids.append(jid)
        if seniority == "senior":
            senior_ids.append(jid)
        if contract == "freelance":
            freelance_ids.append(jid)

    kanban_ids = {}
    now = _dt.datetime.now().isoformat(timespec="seconds")
    for idx, (title, company, stage) in enumerate(KANBAN_JOBS, start=1):
        applied = 1 if stage in ("applied", "interview", "offer", "rejected") else 0
        _insert(conn, (
            title, company, "RemoteOK", f"https://jobs.example.com/kanban-{idx}",
            "Remote", "500 EUR", "QA, Testing",
            f"{title}.", _iso(idx), _raw(idx), 1, applied, "mid", "freelance",
            "remote", "VALIDÉE", stage, now, 1, 0,
        ))
        row = conn.execute(
            "SELECT id FROM jobs WHERE url = ?", (f"https://jobs.example.com/kanban-{idx}",)
        ).fetchone()
        kanban_ids[stage] = row["id"]

    conn.commit()
    conn.close()
    return {
        "total_display": len(DISPLAY_JOBS),
        "recent_ids": recent_ids,
        "cypress_ids": cypress_ids,
        "senior_ids": senior_ids,
        "freelance_ids": freelance_ids,
        "senior_freelance_ids": sorted(set(senior_ids) & set(freelance_ids)),
        "kanban_ids": kanban_ids,
    }


if __name__ == "__main__":  # pragma: no cover - usage manuel
    import json
    import sys as _sys

    db = _sys.argv[1] if len(_sys.argv) > 1 else "/tmp/jh_e2e.db"
    print(json.dumps(seed_database(db), indent=2))
