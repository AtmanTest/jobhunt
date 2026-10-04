# Stratégie de test — JobHunt (Playwright + GenAI)

Sources : **ISTQB CT-GenAI v1.1** (syllabus, 27/04/2026) · **Playwright docs** (Best Practices, POM,
Test Isolation, Parallel & Sharding) · retours d'architecture E2E grands comptes.
Document de travail — aucun secret.

---

# PARTIE A — Ce que dit ISTQB CT-GenAI (et ce que ça change chez nous)

## A1. Le cadre

| Élément | Valeur |
|---|---|
| Certification | ISTQB Certified Tester – Testing with Generative AI (CT-GenAI), Specialist |
| Version | v1.1 (27/04/2026) — v1.0 le 25/07/2025 |
| Prérequis | **CTFL obligatoire** |
| Examen | 40 QCM, 60 min (+25 % non natif), seuil **65 %** (26/40) |
| Formation accréditée | minimum **13,6 h** (815 min) sur 5 chapitres |
| Distinction | CT-AI = **tester les systèmes d'IA** · CT-GenAI = **utiliser l'IA générative pour tester** |

## A2. Les 5 chapitres

| # | Chapitre | Min | Ce qu'on en fait chez nous |
|---|---|---|---|
| 1 | Introduction à la GenAI pour le test | 100 | Vocabulaire (tokens, contexte, multimodal) |
| 2 | **Prompt engineering** | **365** | Le cœur : nos 6 prompts de rôle |
| 3 | Gestion des risques GenAI | 160 | Hallucinations, biais, données, énergie, Shadow AI |
| 4 | Infrastructure de test LLM | 110 | RAG, agents, fine-tuning / LLMOps |
| 5 | Déploiement en organisation | 80 | Feuille de route, sélection LLM/SLM, compétences |

## A3. Structure d'un prompt : les 6 composants (obligatoires)

1. **Rôle** — qui parle / quelle expertise
2. **Contexte** — objet de test, fonctionnalité, informations utiles
3. **Instruction** — impérative, concise, tâche + exigences
4. **Données d'entrée** — user stories, critères, captures, code, cas existants
5. **Contraintes** — ce que la réponse doit respecter
6. **Format de sortie** — structure attendue

> Règle : un prompt sans les 6 composants est incomplet. C'est le premier critère de revue de nos
> `prompts/*.md`.

## A4. Les 3 techniques cœur

| Technique | Quand l'utiliser | Chez nous |
|---|---|---|
| **Prompt chaining** | tâche décomposable, vérification intermédiaire | **toute la chaîne WF2** : PO → Architecte → QA → Dev → CI → Review → Fix. Chaque sortie est vérifiée avant d'alimenter la suivante |
| **Few-shot** (0/1/few) | comportement à illustrer par l'exemple | agent QA : 2-3 cas de test existants en exemple → Gherkin/Playwright conformes au style maison |
| **Meta prompting** | optimiser/co-écrire un prompt | « améliore ce prompt de rôle QA pour qu'il produise moins d'hallucinations » |

**System prompt vs user prompt** : notre `SOUL.md` = system prompt (rôle, contexte, contraintes,
stables) ; le message du nœud = user prompt (tâche du moment). Ne pas mélanger.

## A5. Évaluer le résultat (indispensable, c'est la partie qu'on oublie)

**Métriques** (à définir AVANT de générer) : exactitude · précision · rappel · pertinence ·
diversité · taux de succès d'exécution · efficacité temporelle.

**Techniques de raffinement** : modification itérative · **A/B testing de prompts** · analyse de
sortie (chercher l'écart avec la base de test) · intégration du retour des testeurs · ajustement
longueur/spécificité.

> Traduction concrète : chaque prompt de rôle doit avoir **un jeu de cas étalon** (comme
> `tests/fixtures/ct_ai/matcher_gold.json` qui existe déjà) et un score mesuré. Sans métrique, un
> prompt est une opinion.

## A6. Risques à couvrir (chapitre 3)

Hallucinations · erreurs de raisonnement · biais · **non-déterminisme** · fuite de données /
confidentialité · vulnérabilités (injection de prompt) · consommation énergétique · **Shadow AI**.

Réponses minimales : sortie toujours **vérifiée** avant usage, aucun secret dans un prompt,
température basse pour les tâches déterministes, journalisation des prompts et de leurs sorties.

## A7. Adoption (chapitre 5)

Shadow AI · stratégie GenAI · **sélection LLM vs SLM** (coût/latence/confidentialité) · phases
d'adoption · compétences. Chez nous : DeepSeek pour le raisonnement, LM Studio local pour le
zéro-coût et la souveraineté — c'est exactement l'argument à tenir en entretien.

---

# PARTIE B — Bonnes pratiques Playwright (doc officielle + retours terrain)

## B1. Philosophie (source : Playwright, Best Practices)

1. **Tester le comportement visible par l'utilisateur**, jamais les détails d'implémentation
   (classe CSS, nom de fonction, structure du DOM).
2. **Isoler chaque test** : contexte, cookies, localStorage, données propres.
3. **Ne pas tester ce qu'on ne contrôle pas** (sites tiers, analytics) → `page.route()`.
4. **Se préparer à paralléliser dès l'écriture** : un test qui dépend de l'ordre n'est pas un test.

## B2. Locators

| Priorité | Locator | Exemple |
|---|---|---|
| 1 | `get_by_role` | `page.get_by_role("button", {name:"Submit"})` |
| 2 | `get_by_label` | `page.get_by_label("Email")` |
| 3 | `get_by_text` | libellés métier stables |
| 4 | `data-testid` | quand aucun rôle/texte stable |
| ✗ | CSS / **XPath** | cassent à chaque refonte |

- **Chaining + filter** pour rester robuste : `get_by_role("listitem").filter(has_text="Product 2")`.
- `codegen` / extension VS Code pour **générer** un locator, pas pour le deviner.

## B3. Assertions

- **Web-first assertions** uniquement : `await expect(loc).to_be_visible()` (auto-attente + retry).
- ❌ `expect(await loc.is_visible()).to_be(True)` → aucun retry, test instable.
- `expect.soft()` quand on veut vérifier plusieurs choses et tout remonter.
- ❌ **jamais `wait_for_timeout`** : soit le locator est bon, soit l'assertion gère l'attente.

## B4. Architecture des fixtures (le cœur du sujet)

Toutes les ressources ont un **cycle de vie** :

| Ressource | Portée |
|---|---|
| navigateur | worker (géré par Playwright) |
| contexte + page | **test** (isolation garantie) |
| Page/Component object | test |
| données mutables (commande, profil) | **test** |
| compte/service coûteux et immuable | worker, **seulement si lecture seule** |

- **Fixtures > `beforeEach`/`afterEach`** : composables, typées, teardown garanti même en échec.
- Teardown dans un `try/finally` autour de `use()` → pas de données orphelines.
- ❌ `auto: true` à tout va : comportement invisible dans le fichier de test.
- ❌ `beforeAll` pour l'auth API : le jeton expire, le retry pollue, le cleanup saute.

## B5. Isolation des données (cause n°1 de flakiness)

1. Chaque test **crée ses données**, jamais de base partagée mutable.
2. **Identifiants uniques par worker** :
   - `workerIndex` → unique sur tout le run (change au redémarrage du worker)
   - `parallelIndex` → slot stable (0..workers-1), pour un **pool** pré-provisionné de taille ≥ workers
3. Créer via **API**, pas via l'UI (setup plus rapide, moins fragile).
4. Cleanup en `try/finally` **+** politique d'expiration (un kill de process ne nettoie rien).
5. Setup **idempotent** (upsert / check-before-create) sinon le retry échoue sur les restes du 1er essai.
6. `storageState` : généré par un **projet setup** à chaque run, **jamais commité**.

## B6. Parallélisme et CI

- `workers` = exécution concurrente **sur une machine** ; `--shard` = découpage **sur plusieurs machines**.
- `fullyParallel: true` **seulement** si les tests sont réellement indépendants.
- Rapports : reporter **`blob`** par shard → job de merge (`merge-reports`) → un seul HTML complet.
- Tags de sélection : `@smoke` (PR), suite complète (merge sur main), `@slow` (nuit).
- Ordre obligatoire : **isolation d'abord, concurrence ensuite**. L'inverse produit des semaines de chasse au fantôme.

## B7. Anti-flaky (à traiter comme de l'ingénierie)

1. Rendre déterministe (données, attentes, pas de partage).
2. **Quarantaine tracée** : sortie du chemin bloquant + ticket + **propriétaire**.
3. **Mesurer** le taux de flakiness comme métrique de premier ordre.
4. `failOnFlakyTests: true` pour qu'un retry ne masque pas un vrai bug.
5. Diagnostiquer : `--workers=1` vs `--workers=4`, `--repeat-each=20 --retries=0`.

## B8. Observabilité

- `trace: on-first-retry` en CI (ou `retain-on-failure` pour garder l'échec initial).
- Trace viewer > vidéos/captures pour le diagnostic.
- Statut par test, par shard, par projet ; artefact nommé avec la tentative du workflow.
- Le job de test reste un **check requis** : le job de rapport ne le remplace pas.

## B9. Les 6 anti-patterns qui pourrissent une suite

1. **God Page Object** (une classe pour toute l'app).
2. **POM qui assertent** → l'échec pointe le POM, pas le scénario.
3. **Assertions sur l'implémentation** (classe CSS, id interne).
4. **Fixture dépendante de l'ordre**.
5. **`data-testid` là où `get_by_role` suffit** (on jette le signal d'accessibilité gratuit).
6. **`wait_for_timeout`** au lieu d'une assertion auto-attendante.

---

# PARTIE C — Refonte des tests Playwright JobHunt

## C1. État actuel (constat honnête)

- `tests/playwright/` = **un fichier `test_dashboard.py`** + `scenarios/*.feature` + `run_all.py`.
- `run_all.py` code en dur : `PW_PYTHON = "/tmp/pw_venv/bin/python3"` (**chemin d'une machine, inexistant en CI**),
  8 scénarios listés à la main, pas de tags, lance 1 sous-processus par scénario.
- Pas de `conftest.py` Playwright, pas de Page Object, pas d'auth factorisée, pas de traces,
  pas de parallélisme, pas de projet `setup`.
- Résultat : suite **non isolée**, **non parallélisable**, **non exploitable en CI**, diagnostic impossible.

## C2. Cible

```
tests/playwright/
├── conftest.py              # fixtures : page d'app, auth, données, traces
├── pytest.ini / pyproject   # base-url, tags, timeouts, retries CI
├── auth/
│   └── storage_state.py     # projet "setup" → storageState par rôle (jamais commité)
├── pages/                   # Page Objects (retournent locators/état, n'assertent pas)
│   ├── dashboard_page.py
│   ├── filters_component.py
│   └── kanban_component.py
├── fixtures/
│   ├── jobs.py              # fabriques branchées sur tests/data/factories.py
│   └── api.py               # création via API, pas via UI
├── specs/
│   ├── smoke/               # @smoke : parcours minimal, à chaque PR
│   ├── dashboard/           # affichage, stats, top matches
│   ├── filters/             # remote, pays, séniorité, recherche
│   └── kanban/              # pipeline
└── reports/                 # artefacts (déjà présent, .gitkeep)
```

## C3. Règles de la refonte

1. **Pyramide** : contrats JSON Schema (fait) → API → BDD → **UI réduit aux parcours critiques**.
2. UI = parcours utilisateur, **jamais** la vérification de style.
3. Un **Page Object = interactions**, l'assertion reste dans le spec.
4. Données créées via **API/seed**, libérées en teardown ; identifiants **uniques par worker**.
5. Auth : un **storageState par rôle**, généré une fois par run.
6. Tags : `@smoke` (PR, workers élevés, 1 navigateur) · `@regression` · `@slow` (nuit).
7. Traces `on-first-retry` ; rapport HTML + blob par shard.
8. Toute UI nouvelle → `data-testid` ajouté côté template **avant** d'écrire le test.
9. Aucun chemin d'exécution codé en dur (Python, base-url) — tout vient de `config/environments.py`.
10. Un test rouge = un ticket ; ≥2 échecs non reproductibles = quarantaine.

## C4. Plan par lots

| Lot | Contenu | Critère de sortie |
|---|---|---|
| 0 | squelette + fixtures + projet setup auth | `--collect-only` propre, 1 test de fumée vert |
| 1 | `@smoke` : page charge, titre, 4 cartes stats | vert en CI, < 60 s |
| 2 | dashboard : cartes, top matches, pagination | vert en parallèle (`-n 4`) |
| 3 | filtres : remote, pays, recherche | données créées par l'API, zéro `sleep` |
| 4 | kanban : colonnes, déplacement | idempotent, rejouable |
| 5 | CI : sharding + blob + merge + artefacts | 1 run complet < 5 min, rapport unifié |

## C5. Definition of Done d'un test UI

- [ ] Locator `get_by_role`/`get_by_label` en priorité, jamais XPath
- [ ] Aucun `wait_for_timeout`, aucune assertion manuelle non attendue
- [ ] Page Object si >1 interaction sur le même écran
- [ ] Données créées et nettoyées par le test, identifiant unique
- [ ] Vert en `--workers=1` **et** `--workers=4`
- [ ] Trace disponible en cas d'échec
- [ ] TNR complet vert avant push

---

# PARTIE D — Ce que ça donne en entretien

Trois phrases à retenir :

1. « La chaîne PO → Architecte → QA → Dev → CI → Review est de l'**enchaînement de prompts avec
   vérification intermédiaire** — le pattern que le syllabus CT-GenAI appelle *prompt chaining*. »
2. « Les prompts sont des artéfacts **versionnés**, avec un **jeu d'évaluation** et des **métriques**
   (exactitude, pertinence, taux de succès) — pas des réglages jetables. »
3. « L'UI Playwright est **isolée, parallélisable et tracée** : isolation d'abord, concurrence
   ensuite, et un taux de flakiness mesuré. »
