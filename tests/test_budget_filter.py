"""Filtre par budget minimum (TJM) — écrit AVANT le code (TDD, étape rouge).

Règle métier validée avec le PO :
  - une offre dont le TJM analysé est >= budget_min est retenue ;
  - une offre exactement au budget minimum est retenue (borne inclusive) ;
  - une offre sans budget renseigné est EXCLUE (on ne suppose pas un budget absent) ;
  - budget_min absent (None) ou nul => aucun filtrage ;
  - l'ordre d'entrée des offres est conservé (le tri est une autre responsabilité).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from matcher import filtrer_par_budget  # noqa: E402


def _offre(titre, salaire):
    return {"id": titre.lower().replace(" ", "-"), "title": titre, "salary": salaire,
            "description": "", "location": "Paris", "tags": ""}


OFFRES = [
    _offre("Offre 900", "900 €/jour"),
    _offre("Offre 600", "600-700 €/jour"),      # analysé à 650
    _offre("Offre 520", "520 €/jour"),
    _offre("Offre sans budget", ""),
    _offre("Offre budget illisible", "rémunération à discuter"),
]


class TestFiltreBudget:
    def test_borne_inclusive_au_seuil(self):
        """Une offre exactement au budget minimum doit être retenue."""
        retenues = filtrer_par_budget([_offre("Offre 600 pile", "600 €/jour")], 600)
        assert [o["title"] for o in retenues] == ["Offre 600 pile"]

    def test_moyenne_de_plage_utilisee_comme_tjm(self):
        """« 600-700 €/jour » est analysé à 650 : retenue à 600, exclue à 700."""
        assert filtrer_par_budget([_offre("Plage", "600-700 €/jour")], 600) != []
        assert filtrer_par_budget([_offre("Plage", "600-700 €/jour")], 700) == []

    def test_offres_sans_budget_exclues(self):
        retenues = filtrer_par_budget(OFFRES, 500)
        titres = [o["title"] for o in retenues]
        assert "Offre sans budget" not in titres
        assert "Offre budget illisible" not in titres

    def test_budget_absent_ne_filtre_rien(self):
        assert len(filtrer_par_budget(OFFRES, None)) == len(OFFRES)

    def test_budget_zero_conserve_toutes_les_offres_chiffrees(self):
        titres = [o["title"] for o in filtrer_par_budget(OFFRES, 0)]
        assert titres == ["Offre 900", "Offre 600", "Offre 520"]

    def test_ordre_d_entree_conserve(self):
        titres = [o["title"] for o in filtrer_par_budget(OFFRES, 500)]
        assert titres == ["Offre 900", "Offre 600", "Offre 520"]

    def test_entrees_invalides_ne_plante_pas(self):
        assert filtrer_par_budget([], 600) == []
        assert filtrer_par_budget(None, 600) == []
        assert len(filtrer_par_budget([{"title": "x", "salary": None}], 0)) == 0

    # ------------------------------------------------------------------
    # Niveau intégration : le filtre branché sur l'API des offres
    # ------------------------------------------------------------------

    def test_api_accepte_le_parametre_budget(self):
        """GET /api/jobs?budget_min=600 répond 200 et renvoie une liste."""
        import os as _os
        import sys as _sys
        _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))
        from app import app as application
        client = application.test_client()
        reponse = client.get("/api/jobs?budget_min=600")
        assert reponse.status_code == 200
        assert isinstance(reponse.get_json(), list)

    def test_api_le_filtre_ne_rajoute_jamais_d_offres(self):
        """Invariant : filtrer par budget ne peut que réduire l'ensemble."""
        import os as _os
        import sys as _sys
        _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))
        from app import app as application
        client = application.test_client()
        sans = client.get("/api/jobs").get_json() or []
        avec = client.get("/api/jobs?budget_min=600").get_json() or []
        assert len(avec) <= len(sans)

    def test_api_toutes_les_offres_retournees_respectent_le_seuil(self):
        """Aucune offre sous le seuil ne doit passer le filtre."""
        import os as _os
        import sys as _sys
        _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))
        from app import app as application
        from matcher import analyze_tjm as _analyser
        client = application.test_client()
        offres = client.get("/api/jobs?budget_min=550").get_json() or []
        for offre in offres:
            tjm = _analyser(offre).get("tjm")
            assert tjm is not None and tjm >= 550, f"offre sous le seuil retournée : {offre.get('title')}"

    @pytest.mark.parametrize("seuil,attendu", [
        (900, ["Offre 900"]),
        (650, ["Offre 900", "Offre 600"]),
        (651, ["Offre 900"]),
        (520, ["Offre 900", "Offre 600", "Offre 520"]),
        (1000, []),
    ])
    def test_valeurs_limites(self, seuil, attendu):
        """Analyse des valeurs limites sur le seuil de budget (technique CTFL ch. 4)."""
        titres = [o["title"] for o in filtrer_par_budget(OFFRES, seuil)]
        assert titres == attendu
