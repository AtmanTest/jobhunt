"""Conventions et helpers pour les données de test des parcours UI.

Les données sont construites via `tests/data/factories.py` (source unique de vérité)
et, dès que possible, créées par l'API plutôt que par l'UI.
"""

from __future__ import annotations

from tests.data.factories import job, offer

__all__ = ["job", "offer"]
