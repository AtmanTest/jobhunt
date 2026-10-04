# Passerelle LLM — LiteLLM

Tous les appels de la chaîne d'agents passent par une passerelle **auto-hébergée**.
Elle sert à deux choses que l'appel direct à l'API ne permettait pas : **savoir**
ce que coûte chaque étape, et **plafonner** avant la facture.

## Où ça tourne

| Élément | Valeur |
|---|---|
| Passerelle | `http://127.0.0.1:4000` — **loopback uniquement** (le `0.0.0.0` visible dans les logs est l'écoute *interne* au conteneur) |
| Interface d'admin | `http://127.0.0.1:4000/ui` |
| Base | conteneur `litellm-db` (Postgres 16) — **aucun port publié**, joignable seulement depuis le réseau interne |
| Réseau partagé | `n8n_default` → n8n et Hermes joignent la passerelle en `http://litellm:4000` |
| Fichiers | `~/litellm/` — `docker-compose.yml`, `config.yaml`, `.env` (droits `600`) |

## La chaîne d'agents

`workflows/build_wf2.py` pointe sur la passerelle et présente une **clé virtuelle**
plafonnée — jamais la clé de fournisseur :

- alias `jobhunt-agents`, modèle autorisé `deepseek-flash` (+ `local-qwen`)
- **5 $ / 30 jours**, 60 requêtes/minute
- la clé de fournisseur reste chiffrée en base et n'est jamais exposée au workflow

## Ce que la passerelle a appris, et qui a changé le code

Elle refuse tout paramètre non déclaré. C'est ce qui a rendu visible un point
invisible en appel direct : **`thinking` ne doit pas être un paramètre de premier
niveau**, il doit voyager dans `extra_body`.

Mesuré sur la même question, même modèle :

| Requête | Tokens de raisonnement | Tokens de sortie |
|---|---|---|
| sans rien | 28 | 37 |
| `extra_body.thinking = disabled` | — | **8** |

Autrement dit, l'ancienne écriture faisait payer du raisonnement à chaque appel.
Elle est corrigée dans `workflows/build_wf2.py`.

⚠️ **Ne jamais activer `drop_params`.** Il ferait disparaître `thinking` en
silence : DeepSeek se remettrait à raisonner, le budget de sortie partirait en
raisonnement et `message.content` reviendrait **vide** — soit exactement le bug
corrigé. Mieux vaut une erreur bruyante.

## Comment vérifier la dépense

```bash
# par clé
curl -s "http://127.0.0.1:4000/spend/keys" -H "Authorization: Bearer $LITELLM_MASTER_KEY"

# journal brut
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" litellm-db \
  psql -U llmuser -d litellm -c \
  'select "startTime", model, prompt_tokens, completion_tokens, spend
     from "LiteLLM_SpendLogs" order by "startTime" desc limit 20;'
```

Le compteur d'une clé se met à jour **de façon différée** (tâche planifiée) :
juste après un appel, `x-litellm-response-cost` est exact dans la réponse, mais
`/key/info` peut afficher l'ancien total pendant quelques dizaines de secondes.

## Limites assumées

- Les tarifs sont ceux du catalogue LiteLLM au moment de l'installation. DeepSeek
  **double ses prix en heures pleines** : le chiffre est un outil de pilotage, pas
  une facture. À réconcilier avec la facture fournisseur.
- Le modèle `local-qwen` (LM Studio sur l'hôte) est déclaré à coût nul ; il ne sert
  que si la chaîne le choisit explicitement.
