# Workflows n8n — versionnés dans le dépôt

Les workflows sont du **code** : ils vivent ici, se relisent en pull request et se
régénèrent. On ne les édite pas à la main dans l'interface n8n.

## Chaîne d'agents — `wf2_agents.json`

```
Issue GitHub (label agent:go)
   │  sondage sortant toutes les 5 min — n8n reste en 127.0.0.1,
   │  aucun port n'est ouvert pour recevoir un webhook GitHub
   ▼
PO ──► Spec Review ──┬──► Architecte ──► QA ──► Dev ──► branche + specs + commit + PR
                     │      (NO-GO ──► fin, on ne code pas)
                     ▼
                   CI (rattachée au SHA produit) ──► QA Review ──► rapport dans la PR
                                                  └── échec ──► Fix (max 3) ──► CI
```

33 nœuds, 7 appels LLM, 7 appels GitHub API, 1 déclencheur.

### Ce que la chaîne écrit réellement

Contrairement à la version précédente, elle **écrit dans le dépôt** :

| Étape | Action |
|---|---|
| `Préparer l'écriture` | transforme la réponse de l'agent Dev en fichiers |
| `Créer la branche` | `git/refs` depuis `main` |
| `Écrire les fichiers` | API Contents, un appel par fichier |
| — | plus les artefacts `specs/<issue>/spec.md`, `review.md`, `plan.md` |
| `Ouvrir la PR` | pull request vers `main` |
| `CI — statut` | `actions/runs?head_sha=<sha produit>` — **rattaché au commit produit**, et non au dernier run du dépôt |
| `Poster le rapport` | commentaire de PR |
| `Marquer traitée` / `Retirer la demande` | étiquettes `agent:done` / `agent:go` — idempotence |

### Les prompts ne sont pas dans le workflow

Ils sont lus dans `prompts/*.md` **au moment de la génération**. Le workflow
embarque leur copie exacte : impossible de dériver silencieusement du dépôt.
`build_wf2.py --check` échoue si les deux divergent.

## Régénérer

```bash
python workflows/build_wf2.py            # écrit wf2_agents.json depuis prompts/*.md
python workflows/build_wf2.py --check    # échoue si le JSON a dérivé
```

## Importer dans n8n

⚠️ L'import **désactive** le workflow : importer, publier, puis redémarrer le
conteneur — dans cet ordre, sinon le déclencheur n'est pas chargé.

```bash
docker cp workflows/wf2_agents.json n8n:/tmp/wf2_agents.json
docker exec -u node n8n n8n import:workflow --input=/tmp/wf2_agents.json
docker exec -u node n8n n8n publish:workflow --id=wf2agentsjobhunt
docker restart n8n
```

## Économie de tokens

Voir `docs/token-economy.md`. En résumé : prompt de rôle **stable en tête**
(mis en cache), chaque étape ne reçoit que l'artefact précédent, `max_tokens`
plafonné par rôle, artefacts **écrits par fichier** plutôt que recopiés d'un
prompt à l'autre, arborescence transmise en **noms seuls**, boucle bornée à 3.

## Prérequis sur le jeton GitHub

Le jeton doit porter, sur `AtmanTest/jobhunt` :

- **Issues : Read and write** (lire les tickets, poser les étiquettes) ;
- **Contents : Read and write** (branche, fichiers) ;
- **Pull requests : Read and write** ;
- **Actions : Read** (porter le verdict de CI).

Sans « Issues », la chaîne s'arrête au premier nœud : elle ne voit aucun ticket.
