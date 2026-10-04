"""Exécution des fonctions de PRODUCTION sur la connexion SQLite de test.

Les steps BDD doivent exercer le vrai code produit (dédoublonnage de
``scraper.save_jobs``, parsers de scraping) tout en écrivant dans la base de
test. Ces helpers patchent ``scraper.get_db`` pour qu'il retourne la connexion
de test le temps de l'appel, sans jamais la fermer (sinon le fixture suivant
perdrait sa base).
"""

# Champs obligatoires lus par ``scraper.save_jobs`` et absents des dicts JSON
# écrits directement dans les .feature (ex. {"title", "company", "url"}).
_DEFAULTS = {
    "company": "",
    "source": "TestSource",
    "location": "Worldwide",
    "salary": "",
    "tags": "",
    "description": "",
    "date": "",
    "raw_date": 0,
}


def normalize_job(job):
    """Complète un dict d'offre avec les champs requis par ``save_jobs``."""
    normalized = dict(_DEFAULTS)
    normalized.update(job)
    return normalized


class _NonClosingConnection:
    """Proxy qui délègue tout à la connexion, sauf ``close()`` (no-op)."""

    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        pass


def save_jobs_against(conn, jobs):
    """Appelle ``scraper.save_jobs`` sur ``conn`` (dédoublonnage production).

    Returns:
        Nombre de nouvelles lignes réellement insérées.
    """
    import scraper

    original_get_db = scraper.get_db
    wrapped = _NonClosingConnection(conn)

    def _test_get_db():
        return wrapped

    scraper.get_db = _test_get_db
    try:
        return scraper.save_jobs([normalize_job(j) for j in jobs])
    finally:
        scraper.get_db = original_get_db


def fetch_and_save_against(conn, fetcher, *args, **kwargs):
    """Exécute ``fetcher`` (scraper) puis insère via ``save_jobs`` sur ``conn``.

    Returns:
        (liste des offres récupérées, nombre de nouvelles lignes insérées)
    """
    jobs = fetcher(*args, **kwargs)
    inserted = save_jobs_against(conn, jobs)
    return jobs, inserted
