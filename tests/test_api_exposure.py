"""Non-régression : aucun endpoint public ne doit exposer la clé ni le crédit API.

Origine du défaut :
  - `/api/deepseek/balance` renvoyait le solde du compte API à n'importe quel
    visiteur, sans authentification (dépôt public + service déployé) ;
  - `/api/jobs/enrich/<id>` consommait la clé LLM au nom de n'importe qui.

Correctifs couverts ici :
  - la route du solde est supprimée (aucun appel au endpoint « balance » du
    fournisseur ne subsiste dans le code) ;
  - le widget de solde est retiré du dashboard ;
  - `/api/jobs/enrich/<id>` n'accepte plus les requêtes venant d'un
    déploiement public (proxy / production) sans jeton explicite.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import app, _llm_api_allowed  # noqa: E402

RACINE = Path(__file__).resolve().parent.parent
IGNORES = {".git", "node_modules", ".venv", "venv", "__pycache__", "reports"}


class TestCreditApiNonExpose:
    def test_route_balance_supprimee(self):
        """L'endpoint qui lisait le solde n'existe plus."""
        reponse = app.test_client().get("/api/deepseek/balance")
        assert reponse.status_code == 404, (
            "/api/deepseek/balance répond encore : le solde reste exposé publiquement"
        )

    def test_dashboard_sans_widget_de_solde(self):
        """Le dashboard ne doit plus afficher ni interroger le solde."""
        html = (RACINE / "templates" / "dashboard.html").read_text(encoding="utf-8")
        assert "balance-header" not in html
        assert "/api/deepseek/balance" not in html

    def test_plus_aucun_appel_au_solde_dans_le_code(self):
        """Contrôle générique : plus une seule ligne n'appelle balance_infos."""
        coupables = []
        for chemin in RACINE.rglob("*"):
            if not chemin.is_file() or chemin.suffix not in {".py", ".html", ".js"}:
                continue
            if IGNORES & set(chemin.parts):
                continue
            if chemin.resolve() == Path(__file__).resolve():
                continue  # ce test cite la chaîne recherchée : il ne se compte pas
            texte = chemin.read_text(encoding="utf-8", errors="ignore")
            if "api.deepseek.com/user/balance" in texte:
                coupables.append(str(chemin.relative_to(RACINE)))
        assert not coupables, f"appel au solde encore présent dans : {coupables}"

    def test_aucune_route_de_solde_declaree(self):
        routes = [str(r) for r in app.url_map.iter_rules()]
        fautives = [r for r in routes if "balance" in r.lower()]
        assert not fautives, f"route liée au solde encore déclarée : {fautives}"


class TestEnrichissementReserveAuLocal:
    """L'enrichissement LLM ne doit pas être déclenchable par un tiers."""

    def test_refuse_derriere_un_proxy_public(self):
        reponse = app.test_client().get(
            "/api/jobs/enrich/1", headers={"X-Forwarded-For": "203.0.113.9"}
        )
        assert reponse.status_code == 403

    def test_refuse_en_production(self, monkeypatch):
        monkeypatch.setenv("RENDER", "true")
        reponse = app.test_client().get("/api/jobs/enrich/1")
        assert reponse.status_code == 403

    def test_autorise_en_local(self):
        with app.test_request_context("/api/jobs/enrich/1"):
            assert _llm_api_allowed() is True

    def test_autorise_avec_jeton(self, monkeypatch):
        monkeypatch.setenv("JOBHUNT_API_TOKEN", "jeton-de-test")
        monkeypatch.setenv("RENDER", "true")
        with app.test_request_context(
            "/api/jobs/enrich/1", headers={"X-JobHunt-Token": "jeton-de-test"}
        ):
            assert _llm_api_allowed() is True

    def test_jeton_faux_refuse(self, monkeypatch):
        monkeypatch.setenv("JOBHUNT_API_TOKEN", "jeton-de-test")
        monkeypatch.setenv("RENDER", "true")
        with app.test_request_context(
            "/api/jobs/enrich/1", headers={"X-JobHunt-Token": "mauvais-jeton"}
        ):
            assert _llm_api_allowed() is False
