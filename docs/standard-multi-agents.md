# Standard multi-agents — JobHunt

Chaîne d'agents pilotée, du **ticket à la pull request**. Référentiels appliqués :
**ISTQB CTFL v4.0**, **ISTQB CT-GenAI v1.1**, **PSPO I & II**, bonnes pratiques d'ingénierie.

---

## 1. Vue d'ensemble

```
   ┌──────────────────────────────┐
   │  ENTRÉE — issue GitHub       │  3 formulaires structurés :
   │  Bug · User story · Tâche    │  les exigences vivent dans le ticket,
   └──────────────┬───────────────┘  jamais dans un prompt jetable
                  │  webhook `issues` · label `agent:go`
                  ▼
   ┌──────────────────────────────────────────────────────────────┐
   │  PO ─────────► Spec Review ─────► Architecte ─────► QA       │
   │  valeur, AC     attaque la spec    plan, impact     cas de    │
   │  testables      (verdict GO)       données          test      │
   └──────────────────────────────┬───────────────────────────────┘
                                  ▼
   ┌──────────────────────────────────────────────────────────────┐
   │  Dev (branche) ──► CI GitHub Actions ──► QA Review            │
   │                     lint · tests          verdict green /     │
   │                     empreinte             red / refused       │
   └──────────────────────────────┬───────────────────────────────┘
                        échec     │      succès
                     ┌────────────┘            └──────────┐
                     ▼                                     ▼
              Fix (max 3) ──► CI                     PR + rapport
```

## 2. Les rôles et leur référentiel

| Rôle | Fichier de contrat | Référentiel | Produit |
|---|---|---|---|
| **PO** | `prompts/po.md` | PSPO I & II · CTFL (testabilité) | objectif produit, valeur mesurée, AC `AC-01…` en *Étant donné / Quand / Alors*, hors périmètre, cas limites, risques |
| **Spec Review** | `prompts/spec-review.md` | CTFL (revue) · CT-GenAI (vérification) | verdict `GO` / `GO SOUS CONDITIONS` / `NO-GO` + bloquants |
| **Architecte** | `prompts/architecte.md` | ingénierie (ADR) · CTFL (testabilité) | décisions + alternative écartée, impact données/interfaces, point de testabilité |
| **QA** | `prompts/qa.md` | **CTFL v4.0** techniques · CT-GenAI (données synthétiques) | traçabilité `AC → CT`, cas Gherkin, techniques nommées, cas négatifs, critères de sortie |
| **Dev** | `prompts/dev.md` | bonnes pratiques dev | branche dédiée, commits conventionnels, diff minimal, tests d'abord |
| **QA Review** | `prompts/qa-review.md` | CTFL (rapport, critères de sortie) | verdict, comparaison d'empreinte, couverture réelle, ce qui manque |
| **Fix** | `prompts/fix.md` | CTFL (cause racine, non-régression) | cause racine, correction minimale, **test de non-régression obligatoire** |

## 3. Les quatre portes de qualité

| Porte | Question posée | Preuve exigée | Échec |
|---|---|---|---|
| **1. Spec Review** | la spécification permet-elle d'implémenter sans deviner ? | verdict + bloquants | `NO-GO` : on ne code pas |
| **2. Critères testables** | chaque AC est-il vérifiable automatiquement ? | table `AC → CT` | AC non testable = AC réécrit |
| **3. CI** | le commit testé est-il bien celui proposé ? | `fingerprint_tested` vs `fingerprint_head` | empreinte différente → `refused` |
| **4. QA Review** | le comportement livré couvre-t-il les critères ? | verdict + preuves par test | `red` → boucle Fix (max 3) |

Le verdict est journalisé dans la table `gates` :
`green` · `red` · `refused`. Un `refused` n'est pas un échec de test, c'est un refus de certifier.

## 4. L'entrée : trois formulaires, aucun champ libre

| Formulaire | Fichier | Champs structurants |
|---|---|---|
| **🐞 Bug** | `.github/ISSUE_TEMPLATE/1-bug.yml` | reproduction, attendu, obtenu, sévérité, environnement, **technique CTFL qui aurait dû le détecter**, **test de non-régression à ajouter** (obligatoire) |
| **🧭 User story** | `.github/ISSUE_TEMPLATE/2-user-story.yml` | Product Goal, valeur mesurée, hypothèses, **AC Gherkin**, **hors périmètre**, cas limites, données de test, risques (dont risques IA), Definition of Done |
| **🔧 Tâche technique** | `.github/ISSUE_TEMPLATE/3-tache-technique.yml` | contexte, résultat observable, contraintes, plan de vérification, impact/rollback, DoD dev |

Le formulaire libre est désactivé (`blank_issues_enabled: false`) : une demande sans structure
n'entre pas dans la chaîne.

> **Issue types et issue fields** (métadonnées typées) sont des fonctions **au niveau d'une
> organisation**. Le dépôt appartient à un compte utilisateur : ces deux mécanismes ne sont donc
> pas disponibles ici — la structure est portée par les formulaires eux-mêmes.

## 5. Artefacts et traçabilité

**Dans le dépôt** (versionnés, revus en PR) :

```
specs/<issue>-<slug>/
├── spec.md      # PO : objectif, valeur, AC, hors périmètre, cas limites
├── review.md    # Spec Review : verdict et bloquants
├── plan.md      # Architecte : décisions, impact, testabilité
└── tasks.md     # découpage ordonné par dépendances
prompts/         # les contrats de rôle, source de vérité
```

**Dans Supabase** (exploitables, mesurables) :

| Table | Contenu |
|---|---|
| `runs` | agent, rôle, empreinte, `tokens_in/out`, `cost_usd` |
| `cases` | cas de test, statut, lien de trace |
| `gates` | verdict par porte, empreinte testée vs tête, motif |
| `pipeline_events` | journal en ajout seul de toute la chaîne |
| `deployments` | environnement, commit, URL |

## 6. Ce que la chaîne applique d'ISTQB CT-GenAI

| Concept CT-GenAI | Application concrète |
|---|---|
| Structure de prompt à **6 composants** | rôle · contexte · instruction · données · contraintes · format — dans chaque `prompts/*.md` |
| **Enchaînement de prompts** | la chaîne elle-même, avec vérification à chaque étape |
| **Few-shot** | les cas de test existants servent d'exemples au QA |
| **Méta-prompting** | la Spec Review réécrit la consigne d'entrée, pas la sortie |
| **Hallucination / erreur de raisonnement** | aucune sortie n'est acceptée sans preuve : CI, empreinte, test qui tourne |
| **Non-déterminisme** | verdict fondé sur des faits reproductibles, jamais sur la confiance |
| **Données et vie privée** | formulaires et tests interdisent toute donnée personnelle |
| **Risques de l'adoption** | `Shadow AI` traité : un seul point d'entrée, tracé et versionné |

## 7. Comment on lance

1. Ouvrir une **issue** avec le bon formulaire, poser le label `agent:go`.
2. La chaîne produit les artefacts, ouvre une branche et une pull request.
3. Lire le **rapport de livraison** dans la PR ; le détail est dans `gates` et `pipeline_events`.

Sans label `agent:go`, aucune exécution : rien ne se déclenche implicitement.
