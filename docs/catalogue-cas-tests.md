# Catalogue des cas de test — JobHunt

Compagnon du [plan de stratégie de tests](./strategie-tests.md). Il recense les cas
 de test **conçus** (techniques ISTQB), leur priorité de risque, et l'endroit où ils
sont exécutés.

## Légende

| Symbole | Sens |
|---|---|
| ✅ | implémenté et exécuté dans la TNR |
| ⏳ | conçu, non implémenté |
| 🔒 | verrouillé par empreinte (golden) — toute évolution doit être délibérée |
| 🐞 | défaut constaté, documenté, **non corrigé** (voir §21) |

| Priorité | Sens |
|---|---|
| **P1** | critique : un échec bloque la mise en production |
| **P2** | important : à couvrir, non bloquant |
| **P3** | confort : disponibilité et contenu |

Techniques : **EP** partition d'équivalence · **BVA** valeurs limites ·
**DT** table de décision · **ST** transition d'état · **UC** cas d'utilisation ·
**INV** invariant. Convention d'identifiant : `TC-<MODULE>-<NNN>`.

---

## 1. Synthèse de couverture

| Module | Cas conçus | ✅ | ⏳ | 🐞 | Priorité |
|---|---|---|---|---|---|
| M1 Authentification | 18 | 18 | 0 | 0 | P1 |
| M2 Dashboard | 12 | 12 | 0 | 0 | P1 |
| M3 Recherche & facettes | 9 | 8 | 0 | 1 | P1 |
| M4 Onglets pays | 5 | 5 | 0 | 0 | P1 |
| M5 Kanban | 5 | 5 | 0 | 0 | P1 |
| M6 Cartes & pagination | 6 | 6 | 0 | 0 | P2 |
| M7 Thème & responsive | 4 | 4 | 0 | 0 | P2 |
| M8 API offres, stats & exposition | 16 | 16 | 0 | 0 | P1 |
| M9 Actions sur une offre | 8 | 7 | 0 | 1 | P2 |
| M10 Offres clôturées | 5 | 5 | 0 | 0 | P2 |
| M11 Lettre de motivation | 4 | 4 | 0 | 0 | P2 |
| M12 Enrichissement IA | 4 | 4 | 0 | 0 | P2 |
| M13 Scraping | 14 | 14 | 0 | 0 | P1 |
| M14 Filtrage, matching & scoring IA | 114 | 114 | 0 | 0 | P1 |
| M15 Profil | 5 | 5 | 0 | 0 | P2 |
| M16 Monitoring | 5 | 5 | 0 | 0 | P3 |
| M17 Cockpit QA | 4 | 4 | 0 | 0 | P3 |
| M18 Pages vitrines / POC | 6 | 6 | 0 | 0 | P3 |
| **Total** | **244** | **242** | **0** | **2** |

**Backlog résorbé** : aucun cas conçu ne reste au statut ⏳. Les 2 cas restants sont
des défauts constatés (§21), pas des tests manquants.

Comptes d'exécution vérifiés par la TNR (`bash tests/run_tnr.sh`) :

| Étage | Résultat |
|---|---|
| Cœur (unitaires · API · contrats · BDD backend) | **244 passed**, 6 skipped |
| E2E navigateur (Playwright `@regression`) | **57 passed** |
| BDD navigateur (Gherkin `@frontend`) | **11 passed** |

---

## 2. M1 — Authentification

| ID | Titre | Tech. | Prio | Attendu | Où | Statut |
|---|---|---|---|---|---|---|
| TC-AUTH-001 | La page de connexion s'affiche | EP | P1 | formulaire, email, mot de passe, bouton visibles | `test_login.py` | ✅ |
| TC-AUTH-002 | Le titre identifie l'application | — | P2 | titre contient « JobHunt » | `test_login.py` | ✅ |
| TC-AUTH-003 | Le mot de passe est masqué | — | P1 | `type="password"` | `test_login.py` | ✅ |
| TC-AUTH-004 | Le message d'erreur est masqué au départ | — | P2 | `#error-msg` non visible | `test_login.py` | ✅ |
| TC-AUTH-005 | Un email vide bloque la soumission | BVA | P1 | évènement `invalid`, aucune requête | `test_login.py` | ✅ |
| TC-AUTH-006 | Un email mal formé est invalide | EP | P1 | invalide puis valide | `test_login.py` | ✅ |
| TC-AUTH-007 | Un mot de passe < 6 caractères est invalide | BVA | P1 | `123` invalide ; `123456` valide | `test_login.py` | ✅ |
| TC-AUTH-008 | Basculer vers l'inscription change les libellés | ST | P1 | bouton, sous-titre, lien | `test_login.py` | ✅ |
| TC-AUTH-009 | Rebasculer restaure la connexion | ST | P2 | libellés d'origine | `test_login.py` | ✅ |
| TC-AUTH-010 | Identifiants invalides → message serveur | EP | P1 | 401 stubbé → message, reste sur `/login` | `test_login.py` | ✅ |
| TC-AUTH-011 | Erreur serveur affichée | EP | P1 | 500 stubbé → message | `test_login.py` | ✅ |
| TC-AUTH-012 | Erreur réseau affichée | EP | P1 | requête avortée → « Erreur réseau » | `test_login.py` | ✅ |
| TC-AUTH-013 | Inscription refusée → message serveur | EP | P2 | 400 stubbé → message | `test_login.py` | ✅ |
| TC-AUTH-014 | Connexion réussie → redirection dashboard | UC | P1 | URL `/`, hero visible | `test_login.py` | ✅ |
| TC-AUTH-015 | Menu utilisateur et déconnexion | UC | P2 | menu visible si connecté ; clic → `POST /api/auth/logout` | `test_session.py` | ✅ |
| TC-AUTH-016 | `/api/auth/me` anonyme | EP | P2 | `{"authenticated": false}` | `test_auth_api.py` | ✅ |
| TC-AUTH-017 | `/login` déjà connecté → redirection | ST | P2 | 302 vers `/` | `test_auth_api.py` | ✅ |
| TC-AUTH-018 | Inscription mot de passe trop court → 400 | BVA | P2 | refus **avant** l'appel au fournisseur | `test_auth_api.py` | ✅ |

---

## 3. M2 — Dashboard

| ID | Titre | Prio | Attendu | Où | Statut |
|---|---|---|---|---|---|
| TC-DASH-001 … 005 | Chargement, hero, filtres, liste, aucune erreur JS | P1 | structure servie, `pageerror` vide | `specs/smoke/` | ✅ |
| TC-DASH-006 | Offres affichées et compteur cohérent | P1 | 18 cartes, compteur « 18 offres » | `test_dashboard_load.py` | ✅ |
| TC-DASH-007 | Pagination : 3 cartes par page | P2 | 3 cartes visibles | `test_dashboard_load.py` | ✅ |
| TC-DASH-008 | Aucune erreur console au chargement | P1 | erreurs filtrées = ∅ | `test_dashboard_load.py` | ✅ |
| TC-DASH-009 | Les 4 cartes de stats hero | P2 | Offres QA / Cette semaine / Marchés actifs / Jobs clôturés | `test_dashboard_load.py` | ✅ |
| TC-DASH-010 | « Jobs du jour » sans doublon | P2 | ids uniques | BDD `regression/2026-05-29` | ✅ |
| TC-DASH-011 | Badge NEW pour les offres < 7 jours | P2 | 3 badges dans le panneau actif | `test_dashboard_load.py` | ✅ |
| TC-DASH-012 | Carte « Jobs clôturés » → `/jobclotured` | P3 | navigation | BDD `regression/2026-05-29` | ✅ |

---

## 4. M3 — Recherche & facettes

| ID | Titre | Tech. | Prio | Attendu | Où | Statut |
|---|---|---|---|---|---|---|
| TC-SEARCH-001 | Recherche temps réel filtre les offres | EP | P1 | « Cypress » → 6 offres conformes | `test_search.py` | ✅ |
| TC-SEARCH-002 | Effacer restaure l'état complet | ST | P1 | 18 offres | `test_search.py` | ✅ |
| TC-SEARCH-003 | Recherche insensible à la casse | EP | P1 | « cypress » = « Cypress » | `test_search.py` | ✅ |
| TC-SEARCH-004 | Recherche sans résultat → état vide | EP | P1 | « 0 offres », 0 carte | `test_empty_state.py` | ✅ |
| TC-SEARCH-005 | Facette « senior » | DT | P1 | 8 offres, aucune non-senior | `test_facets.py` | ✅ |
| TC-SEARCH-006 | Filtres combinés senior + freelance | DT | P1 | 5 offres (intersection) | `test_facets.py` | ✅ |
| TC-SEARCH-007 | Réinitialiser la facette restaure tout | ST | P2 | 18 offres | `test_facets.py` | ✅ |
| TC-SEARCH-008 | Recherche par entreprise | EP | P2 | « Globex » → 1 offre | `test_search.py` | ✅ |
| TC-SEARCH-009 | Recherche insensible aux accents | EP | P2 | « Clement » trouve « Clément » | — | 🐞 DE-003 |

---

## 5. M4 — Onglets pays

| ID | Titre | Prio | Attendu | Où | Statut |
|---|---|---|---|---|---|
| TC-TABS-001 | Ouverture par défaut sur la France | P1 | `#panel-france` actif | `test_country_tabs.py` | ✅ |
| TC-TABS-002 | Onglet sans offre → état vide | P1 | `#panel-suisse` + `.empty-state` | `test_country_tabs.py` | ✅ |
| TC-TABS-003 | Onglet « Tous » regroupe tout | P1 | 18 cartes | `test_country_tabs.py` | ✅ |
| TC-TABS-004 | Onglet LinkedIn active son panneau | P2 | `#panel-linkedin` visible | `test_country_tabs.py` | ✅ |
| TC-TABS-005 | Badge de compte par onglet cohérent | P2 | badge = cartes comptées | `test_dashboard.py` | ✅ |

---

## 6. M5 — Kanban candidatures

| ID | Titre | Tech. | Prio | Attendu | Où | Statut |
|---|---|---|---|---|---|---|
| TC-KB-001 | Cinq colonnes par stade | EP | P1 | titres FR + 1 carte par stade | `test_kanban.py` | ✅ |
| TC-KB-002 | Déplacer une carte persiste côté serveur | ST | P1 | `/api/jobs` reflète le nouveau stade | `test_kanban.py` | ✅ |
| TC-KB-003 | Fermeture au clavier (Échap) | — | P2 | overlay masqué | `test_kanban.py` | ✅ |
| TC-KB-004 | Fermeture par le bouton ✕ | UC | P2 | overlay masqué | `test_kanban.py` | ✅ |
| TC-KB-005 | Le déplacement survit à un rechargement | ST | P2 | carte dans la bonne colonne après reload | `test_kanban.py` | ✅ |

---

## 7. M6 — Cartes d'offres & pagination

| ID | Titre | Prio | Attendu | Où | Statut |
|---|---|---|---|---|---|
| TC-CARD-001 | Champs titre/entreprise/salaire/tags | P2 | tous non vides | `test_job_card.py` | ✅ |
| TC-CARD-002 | Lien Apply sûr | P2 | `target=_blank` + `rel=noopener` | `test_job_card.py` | ✅ |
| TC-CARD-003 | ✕ masque la carte sans naviguer | P2 | pas de navigation | `test_dashboard.py` | ✅ |
| TC-CARD-004 | Apply est le seul lien cliquable | P2 | clic ailleurs sans effet | `test_dashboard.py` | ✅ |
| TC-CARD-005 | Pagination fonctionne | P2 | page suivante affichée | `test_dashboard.py` | ✅ |
| TC-CARD-006 | Boutons ‹/› bornés aux extrémités | BVA | `‹` désactivé en page 1, `›` en dernière page | `test_dashboard_load.py` | ✅ |

---

## 8. M7 — Thème & responsive

| ID | Titre | Prio | Attendu | Où | Statut |
|---|---|---|---|---|---|
| TC-UI-001 | Bascule sombre persiste | P2 | fond sombre + `localStorage` | `test_theme.py` | ✅ |
| TC-UI-002 | Choix clair persiste | P2 | préférence relue à froid | `test_theme.py` | ✅ |
| TC-UI-003 | Barre basse mobile (375 px) | P2 | `#sidebar` fixe en bas | `test_mobile.py` | ✅ |
| TC-UI-004 | Colonne unique sur mobile | P2 | largeurs égales | `test_mobile.py` | ✅ |

---

## 9. M8 — API offres, stats & exposition

| ID | Titre | Prio | Attendu | Où | Statut |
|---|---|---|---|---|---|
| TC-API-001 | Toute route déclarée répond | P1 | aucun 404 inattendu | `test_api_routes.py` | ✅ |
| TC-API-002 | `/api/jobs` renvoie une liste JSON | P1 | type liste | `test_api_routes.py` | ✅ |
| TC-API-003 | `/api/jobs` accepte les filtres documentés | P1 | `qa`, `unapplied`, `search`, `source`, `budget_min` | `test_api_routes.py` | ✅ |
| TC-API-004 | Le filtre budget ne rajoute jamais d'offres | P1 | sous-ensemble | `test_budget_filter.py` | ✅ |
| TC-API-005 | Toutes les offres respectent le seuil | P1 | TJM ≥ seuil | `test_budget_filter.py` | ✅ |
| TC-API-006 | Schéma JSON « job » respecté | P1 | `tests/api/schemas/job.schema.json` | `test_contracts_schema.py` | ✅ |
| TC-API-007 | Schéma JSON « offer » respecté | P1 | `offer.schema.json` | `test_contracts_schema.py` | ✅ |
| TC-API-008 | Le contrat rejette une URL invalide | P1 | invalide | `test_contracts_schema.py` | ✅ |
| TC-API-009 | Le contrat rejette un titre manquant | P1 | invalide | `test_contracts_schema.py` | ✅ |
| TC-API-010 | `/api/stats` et `advanced` renvoient les agrégats | P1 | clés attendues | `test_api_routes.py`, BDD `api/` | ✅ |
| TC-API-011 | `?unapplied=1` exclut les offres postulées | P2 | aucune offre `applied` | `test_auth_api.py` | ✅ |
| TC-SEC-001 … 005 | Étanchéité : pas de route de solde, `/debug` protégé | P1-P2 | 403 en public/prod, 200 en local | `test_api_exposure.py` | ✅ |

---

## 10. M9 — Actions sur une offre

| ID | Titre | Tech. | Prio | Attendu | Où | Statut |
|---|---|---|---|---|---|---|
| TC-ACT-001 | Sauvegarder / dé-sauvegarder | ST | P2 | drapeau `saved` basculé | `test_job_actions.py` | ✅ |
| TC-ACT-002 | Marquer comme postulé | ST | P2 | `applied=1` + ligne `applications` | `test_job_actions.py` | ✅ |
| TC-ACT-003 | Ajouter une note | EP | P2 | note persistée | `test_job_actions.py` | ✅ |
| TC-ACT-004 | Mettre à jour le pipeline | ST | P2 | `applications.status` | `test_job_actions.py` | ✅ |
| TC-ACT-005 | Clic marque l'offre comme vue | EP | P2 | `viewed=1` | `test_job_actions.py` | ✅ |
| TC-ACT-006 | Action sur offre inconnue → 404 | EP | P2 | save/apply/enrich | `test_job_actions.py` | ✅ |
| TC-ACT-007 | Le stade Kanban est stocké sans validation d'énumération | EP | P2 | toute valeur acceptée | — | 🐞 DE-002 |
| TC-ACT-008 | Enrichissement : 403 / 400 / 404 | EP | P2 | proxy public refusé, description courte, offre absente | `test_job_actions.py` | ✅ |

---

## 11. M10 — Offres clôturées

| ID | Titre | Prio | Attendu | Où | Statut |
|---|---|---|---|---|---|
| TC-CLOSE-001 | Dismiss → présente dans `dismissed_jobs` | P2 | BDD `persistence/closed_jobs` | BDD | ✅ |
| TC-CLOSE-002 | Restauration depuis `closed_jobs.json` | P2 | BDD `persistence/closed_jobs` | BDD | ✅ |
| TC-CLOSE-003 | Le dashboard masque les offres clôturées | P2 | aucune dans les onglets pays | BDD `frontend/` | ✅ |
| TC-CLOSE-004 | `/jobclotured` liste les offres clôturées | P2 | titre affiché | `test_job_actions.py` | ✅ |
| TC-CLOSE-005 | Pas de doublon par utilisateur | EP | 1 seule ligne après 2 dismiss | `test_job_actions.py` | ✅ |

---

## 12. M11 — Lettre de motivation

| ID | Titre | Prio | Attendu | Où | Statut |
|---|---|---|---|---|---|
| TC-COV-001 | `/cover-letter/<id>` affiche la lettre | P2 | 200, titre + entreprise + lettre | `test_cover_letter.py` | ✅ *(DE-001 corrigé)* |
| TC-COV-002 | Offre inconnue → 404 | P2 | « Job non trouvé » | `test_cover_letter.py` | ✅ |
| TC-COV-003 | `/api/generate-cover/<id>` → JSON | P2 | clé `cover_letter` | `test_cover_letter.py` | ✅ |
| TC-COV-004 | `/api/apply/<id>` enregistre la candidature | P2 | `mark_applied` appelé avec la lettre | `test_cover_letter.py` | ✅ |

---

## 13. M12 — Enrichissement IA

| ID | Titre | Prio | Attendu | Où | Statut |
|---|---|---|---|---|---|
| TC-ENR-001 | Une réponse LLM nulle n'écrase pas | P2 | valeurs du scraper conservées | `test_enrich_preserve.py` | ✅ |
| TC-ENR-002 | Les chaînes vides n'écrasent pas | P2 | idem | `test_enrich_preserve.py` | ✅ |
| TC-ENR-003 | Colonnes vides remplies, vocabulaire normalisé | P2 | `remote_type` normalisé | `test_enrich_preserve.py` | ✅ |
| TC-ENR-004 | Les clés absentes sont tolérées | P2 | pas d'exception | `test_enrich_preserve.py` | ✅ |

---

## 14. M13 — Scraping

| ID | Titre | Prio | Attendu | Où | Statut |
|---|---|---|---|---|---|
| TC-SCRAP-001 … 004 | RemoteOK : nominal, vide, dédoublonnage, exclusions QA | P1 | comportements conformes | BDD `scraping/remoteok` | ✅ |
| TC-SCRAP-005 … 006 | We Work Remotely : nominal, flux indisponible | P1 | dégradation sans crash | BDD `scraping/weworkremotely` | ✅ |
| TC-SCRAP-007 … 009 | Wellfound (Cloudflare), Otta (JS), LinkedIn (RSS) | P2 | échecs gérés proprement | BDD `scraping/*` | ✅ |
| TC-SCRAP-010 … 012 | LinkedIn : URL directe, pas de doublon, keywords FR | P2 | conformes | BDD `regression/2026-05-29` | ✅ |
| TC-SCRAP-013 | `/api/linkedin/jobs` stable sans fichier | P2 | structure vide | `test_api_routes.py` | ✅ |
| TC-SCRAP-014 | `/api/refresh` déclenche le scraping | P2 | `{"status":"started"}` + tâche lancée | `test_auth_api.py` | ✅ |

---

## 15. M14 — Filtrage, matching et scoring IA

| Famille | Nb | Prio | Contenu | Où | Statut |
|---|---|---|---|---|---|
| Filtre budget | 15 | P1 | borne inclusive, moyenne de plage, offres sans budget, budget absent, ordre, entrées invalides, valeurs limites | `test_budget_filter.py` | ✅ |
| Filtre QA | 4 | P1 | « QA Automation » accepté, « Game Tester » rejeté, pharma rejeté, stack reconnue | BDD `filtering/qa_filter` | ✅ |
| Déduplication | 2 | P1 | même URL ; titre + entreprise | BDD `filtering/deduplication` | ✅ |
| Scoring / portes IA | 63 | P1 | corpus étiqueté, matrice de confusion, seuils, bornage, entrées adverses, **invariance**, monotonie, déterminisme | `test_ct_ai_gates.py` | ✅ |
| Livraison virtuelle | 24 | P2 | traçabilité cas→US→CA, campagnes v1/v2, anomalies | `test_virtual_delivery.py` | ✅ |
| Régressions historiques | 3 | P1 | BUG-001 KeyError, BUG-002 « QA Director », BUG-003 casse | BDD `regression/bug_fixes` | ✅ |
| Doublons des sections | 3 | P1 | JOBS DU JOUR / TOP MATCHES sans doublon | BDD `regression/2026-05-29` | ✅ |

---

## 16. M15 — Profil

| ID | Titre | Prio | Attendu | Où | Statut |
|---|---|---|---|---|---|
| TC-PROF-001 | Lecture/modification sans session → 401 | P2 | `Non authentifié` | `test_profile_api.py` | ✅ |
| TC-PROF-002 | Modification sans donnée valide → 400 | P2 | `Aucune donnée valide` | `test_profile_api.py` | ✅ |
| TC-PROF-003 | Champs non autorisés ignorés (liste blanche) | P2 | `role` jamais transmis | `test_profile_api.py` | ✅ |
| TC-PROF-004 | Avatar sans image → 400 | P2 | `Image requise` | `test_profile_api.py` | ✅ |
| TC-PROF-005 | `/settings` servie | P2 | 200 | `test_profile_api.py` | ✅ |

---

## 17. M16 — Monitoring

| ID | Titre | Prio | Attendu | Où | Statut |
|---|---|---|---|---|---|
| TC-MON-001 | Liste des sites structurée | P3 | `{sites, alerts}` | `test_monitoring_api.py` | ✅ |
| TC-MON-002 | URL vide → 400 | P3 | `URL invalide` | `test_monitoring_api.py` | ✅ |
| TC-MON-003 | Ajout idempotent | P3 | 1 seule entrée | `test_monitoring_api.py` | ✅ |
| TC-MON-004 | Suppression effective | P3 | site retiré | `test_monitoring_api.py` | ✅ |
| TC-MON-005 | Sonde sur site inconnu sans effet | P3 | pas d'erreur, aucun site créé | `test_monitoring_api.py` | ✅ |

---

## 18. M17 — Cockpit QA

| ID | Titre | Prio | Attendu | Où | Statut |
|---|---|---|---|---|---|
| TC-QA-001 | Inventaire des cas servi | P3 | JSON | `test_qa_cockpit_api.py` | ✅ |
| TC-QA-002 | Déclenchement sans jeton → 400 | P3 | `GITHUB_TOKEN` explicite, aucun appel sortant | `test_qa_cockpit_api.py` | ✅ |
| TC-QA-003 | Liste des exécutions servie | P3 | clé `runs` | `test_qa_cockpit_api.py` | ✅ |
| TC-QA-004 | Exécution inconnue → `pending` | P3 | pas de 500 | `test_qa_cockpit_api.py` | ✅ |

---

## 19. M18 — Pages vitrines / POC

| ID | Titre | Prio | Attendu | Où | Statut |
|---|---|---|---|---|---|
| TC-PAGE-001 | Toutes les pages répondent | P3 | 200 (ou 302) sur 12 pages | `test_public_pages.py` | ✅ |
| TC-PAGE-002 | `/stats` accessible | P2 | 200 + contenu | BDD `regression/2026-05-29` | ✅ |
| TC-PAGE-003 | `/poc-ct-ai/api/evidence` | P3 | 200 ou 503, jamais 500 | `test_public_pages.py` | ✅ |
| TC-PAGE-004 | `/poc-ct-ai/api/score` : score invariant | INV | variantes casse/accents/espaces → score identique | `test_public_pages.py` | ✅ |
| TC-PAGE-005 | `/poc-delivery/api/scenario` | P3 | JSON | `test_public_pages.py` | ✅ |
| TC-PAGE-006 | `/marche-qa` et pages de contenu | P3 | 200 | `test_public_pages.py` | ✅ |

---

## 20. Couverture des exigences P1

Les 7 modules critiques (M1–M5, M8, M13, M14) sont **intégralement** ✅ : la TNR
peut donc être considérée comme complète sur le périmètre à risque.

---

## 21. Défauts constatés

| Réf. | Module | Description | Statut | Couverture |
|---|---|---|---|---|
| **DE-001** | M11 | `/cover-letter/<id>` renvoyait **500 `TemplateNotFound: cover_letter.html`** : le template référencé n'existait pas, alors que chaque carte d'offre expose un bouton ✉️ vers cette route. | **Corrigé** (template créé) | `test_cover_letter.py` (marqueur `regression`) |
| **DE-002** | M9 | `POST /api/job/<id>/stage` **ne valide pas** la valeur du stade : n'importe quelle chaîne est écrite en base. Aucune énumération n'est appliquée. | Ouvert | non couvert (comportement permissif) |
| **DE-003** | M3 | La recherche est **sensible aux accents** : le filtrage JS fait un `indexOf` brut, donc « Clement » ne trouve pas « Clément ». | Ouvert | non couvert |

**Recommandations** pour DE-002 et DE-003 : valider le stade contre une énumération
et normaliser (retrait des diacritiques) avant comparaison. Un test de
non-régression devra être ajouté **avant** la correction (workflow §9.5 de la
stratégie).

---

## 22. Suite du chantier (au-delà du backlog initial)

Pistes pour les prochaines itérations, non bloquantes :

1. **DE-002 / DE-003** : corriger puis couvrir (2 tests `regression`).
2. **Performance de base** : budget de temps sur le chargement du dashboard (ex. < 2 s).
3. **Accessibilité** : parcours clavier complet (tabulation jusqu'aux filtres).
4. **Job de TNR unique en CI** appelant `tests/run_tnr.sh` (parité poste ↔ CI).
