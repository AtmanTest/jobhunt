"""Fabriques de données de test — source unique de vérité.

Deux modèles coexistent dans JobHunt :
  • ``job()``   → table SQLite ``jobs`` (modèle de l'application / dashboard)
  • ``offer()`` → table Supabase ``offers`` (modèle d'ingestion WF1)

Évite la duplication de JSON à la main et garantit des données déterministes.

Usage :
    from tests.data.factories import job, offer, seed
    seed(db, [job(title="QA Mobile"), job(company="FDJ")])
"""

from __future__ import annotations

import itertools
import uuid
from typing import Any

_counter = itertools.count(1)

# Colonnes de la table SQLite jobs, dans l'ordre d'insertion.
JOB_COLUMNS = [
    "title", "company", "source", "url", "location", "salary", "tags",
    "description", "date", "raw_date", "is_qa", "applied", "cover_letter",
    "notes", "tech_stack", "seniority", "contract_type", "remote_type",
    "salary_min", "salary_max", "currency", "ai_enriched", "saved",
]
_NUMERIC = {"raw_date", "is_qa", "applied", "salary_min", "salary_max", "ai_enriched", "saved"}


def job(**over: Any) -> dict[str, Any]:
    """Une offre au format de la table ``jobs``, surchargeable par mot-clé."""
    n = next(_counter)
    row: dict[str, Any] = {
        "title": f"QA Engineer {n}",
        "company": f"Company {n}",
        "source": "RemoteOK",
        "url": f"https://remoteok.com/remote-jobs/qa-engineer-{n}-{uuid.uuid4().hex[:6]}",
        "location": "Worldwide",
        "salary": "",
        "tags": "QA, Testing",
        "description": "Poste de test automatisé.",
        "date": "2026-05-25",
        "raw_date": 1779571200,
        "is_qa": 1,
        "applied": 0,
        "cover_letter": "",
        "notes": "",
        "tech_stack": None,
        "seniority": None,
        "contract_type": None,
        "remote_type": None,
        "salary_min": None,
        "salary_max": None,
        "currency": None,
        "ai_enriched": 0,
        "saved": 0,
    }
    row.update(over)
    return row


def offer(**over: Any) -> dict[str, Any]:
    """Une offre au format de la table Supabase ``offers`` (ingestion WF1)."""
    n = next(_counter)
    row: dict[str, Any] = {
        "external_id": f"test-{n}-{uuid.uuid4().hex[:6]}",
        "source": "remotive",
        "title": f"QA Engineer {n}",
        "company": f"Company {n}",
        "location": "Europe",
        "remote": True,
        "contract": "full_time",
        "salary": None,
        "url": f"https://example.test/offer/{n}",
        "published_at": None,
        "score": 50,
        "tags": ["qa"],
    }
    row.update(over)
    return row


def seed(db, rows: list[dict[str, Any]]) -> int:
    """Insère des offres dans la base de test. Retourne le nombre inséré.

    Ne remplit que les colonnes réellement présentes dans la table : reste
    compatible si le schéma évolue.
    """
    if not rows:
        return 0
    cols = {r[1] for r in db.execute("PRAGMA table_info(jobs)").fetchall()}
    keys = [c for c in JOB_COLUMNS if c in cols and any(c in r for r in rows)]
    if not keys:
        raise ValueError("aucune colonne commune entre la fabrique et la table jobs")
    placeholders = ", ".join("?" for _ in keys)
    sql = f"INSERT INTO jobs ({', '.join(keys)}) VALUES ({placeholders})"
    values = [[r.get(k, 0 if k in _NUMERIC else "") for k in keys] for r in rows]
    db.executemany(sql, values)
    db.commit()
    return len(rows)


def seed_many(db, count: int, **over: Any) -> int:
    """Insère ``count`` offres variées (pagination, tris, déduplication)."""
    return seed(db, [job(raw_date=1779571200 + i, **over) for i in range(count)])
