"""Configuration par environnement — valeurs publiques uniquement.

Aucun secret : les identifiants viennent de l'environnement
(SUPABASE_URL, DEEPSEEK_API_KEY, ...) ou d'un fichier .env hors dépôt.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    name: str
    base_url: str
    db_url: str
    ui_timeout_ms: int
    api_timeout_s: int
    retries: int


_ENVS = {
    "test": Settings("test", "http://localhost:5050", ":memory:", 5_000, 5, 0),
    "preview": Settings("preview", "https://jobhunt-preview.onrender.com", os.getenv("PREVIEW_DB_URL", ""), 10_000, 15, 1),
    "prod": Settings("prod", "https://jobhunt-1-ar3w.onrender.com", os.getenv("PROD_DB_URL", ""), 15_000, 20, 2),
}


def settings(env: str | None = None) -> Settings:
    """Retourne la configuration de l'environnement demandé.

    L'environnement vient de JOBHUNT_ENV (défaut : test).
    """
    key = (env or os.getenv("JOBHUNT_ENV", "test")).lower()
    if key not in _ENVS:
        raise ValueError(f"environnement inconnu : {key!r} (attendu : {', '.join(_ENVS)})")
    return _ENVS[key]
