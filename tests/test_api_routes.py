"""Non-régression sur les points d'entrée de l'API.

Origine : un test d'intégration écrit pour une nouvelle fonctionnalité a révélé que
`/api/jobs` répondait 404 — la fonction existait, mais son décorateur de route avait
disparu. Les scénarios BDD qui consomment cet endpoint échouaient depuis ce moment.

Ces tests empêchent la réapparition du défaut sous deux formes :
  - l'endpoint attendu répond réellement (test explicite, lisible en revue) ;
  - tout endpoint déclaré dans l'application est joignable (test générique : un
    décorateur perdu, un nom de route fautif ou une fonction orpheline est détecté).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import app  # noqa: E402

client = app.test_client()

ENDPOINTS_ATTENDUS = ["/api/jobs", "/api/stats", "/api/auth/me"]


class TestRoutesApi:
    @pytest.mark.parametrize("route", ENDPOINTS_ATTENDUS)
    def test_endpoint_attendu_accessible(self, route):
        """Un endpoint documenté ne doit jamais devenir orphelin (Anomalie AN-102)."""
        reponse = client.get(route)
        assert reponse.status_code != 404, (
            f"{route} répond 404 : route non déclarée (décorateur manquant ?)")
        assert reponse.status_code < 500, f"{route} répond {reponse.status_code}"

    def test_aucune_route_declaree_ne_renvoie_404(self):
        """Contrôle générique : chaque règle déclarée dans l'application est joignable."""
        problemes = []
        for regle in app.url_map.iter_rules():
            chemin = str(regle)
            if not chemin.startswith("/api/") or regle.arguments:
                continue  # les routes paramétrées sont couvertes par des tests dédiés
            if "POST" not in regle.methods and "GET" not in regle.methods:
                continue
            reponse = client.get(chemin)
            if reponse.status_code == 404:
                problemes.append(chemin)
        assert not problemes, f"routes déclarées mais injoignables : {problemes}"

    def test_api_jobs_renvoie_une_liste_json(self):
        reponse = client.get("/api/jobs")
        assert reponse.status_code == 200
        assert isinstance(reponse.get_json(), list)

    def test_api_jobs_accepte_les_filtres_documentes(self):
        """Les filtres de l'API sont un contrat : ils doivent rester acceptés."""
        for requete in ("/api/jobs?qa=1", "/api/jobs?unapplied=1", "/api/jobs?search=qa",
                        "/api/jobs?budget_min=600"):
            reponse = client.get(requete)
            assert reponse.status_code == 200, f"{requete} → {reponse.status_code}"
            assert isinstance(reponse.get_json(), list)
