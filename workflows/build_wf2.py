#!/usr/bin/env python3
"""Génère `workflows/wf2_agents.json` — la chaîne d'agents JobHunt, en code.

Pourquoi un générateur plutôt qu'un JSON édité à la main dans l'interface n8n :

  * **une seule source de vérité pour les prompts** : ils sont lus dans
    `prompts/*.md` au moment de la génération. Plus de prompt recopié dans un
    nœud Code, qui dérive silencieusement du dépôt (5 644 caractères faisaient
    doublon avant) ;
  * le workflow est **versionné et relu en PR**, comme du code ;
  * il est **régénérable** : `python workflows/build_wf2.py`.

Économie de tokens (voir `docs/token-economy.md`) :
  * le prompt de rôle est le message `system` — partie **stable en tête**, donc
    mise en cache par le fournisseur entre deux exécutions ;
  * chaque étape ne reçoit que **l'artefact de l'étape précédente**, jamais
    l'historique complet ni le ticket entier ;
  * `max_tokens` est plafonné par rôle ;
  * les artefacts sont **écrits dans le dépôt** (`specs/<issue>/…`) au lieu
    d'être recopiés d'un prompt à l'autre ;
  * la boucle de correction est bornée (3 tentatives) ;
  * le routage du modèle est explicite par étape.

Usage:
    python workflows/build_wf2.py            # écrit workflows/wf2_agents.json
    python workflows/build_wf2.py --check    # échoue si le JSON a dérivé
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
PROMPTS = RACINE / "prompts"
SORTIE = Path(__file__).resolve().parent / "wf2_agents.json"

# Rôles : fichier de prompt -> clé utilisée dans le workflow.
ROLES = {
    "PO": "po.md",
    "SpecReview": "spec-review.md",
    "Architecte": "architecte.md",
    "QA": "qa.md",
    "Dev": "dev.md",
    "Fix": "fix.md",
    "QAReview": "qa-review.md",
}

# Économie de tokens : plafond de sortie par rôle, et modèle par étape.
# `hermes-agent` route vers le modèle par défaut du profil ; les étapes
# purement mécaniques peuvent être basculées sur un modèle local (gratuit).
MAX_TOKENS = {
    "PO": 1200,
    "SpecReview": 600,
    "Architecte": 900,
    "QA": 1500,
    "Dev": 4000,
    "Fix": 2000,
    "QAReview": 800,
}
MODELE = {
    "PO": "deepseek-flash",
    "SpecReview": "deepseek-flash",
    "Architecte": "deepseek-flash",
    "QA": "deepseek-flash",
    "Dev": "deepseek-flash",
    "Fix": "deepseek-flash",
    "QAReview": "deepseek-flash",
}

HERMES_URL = "http://hermes:8642/v1/chat/completions"
CRED_HERMES = {"httpHeaderAuth": {"id": "hermesapitoken01", "name": "Hermes API"}}
CRED_GITHUB = {"githubApi": {"id": "githubpatcreds01", "name": "GitHub"}}
CRED_PG = {"postgres": {"id": "supabasepg00001", "name": "Supabase (Postgres)"}}

# Bornes de la boucle de correction.
MAX_TENTATIVES = 3

# Dépôt piloté par la chaîne, et étiquettes du cycle de vie du ticket.
#
# Le déclenchement se fait par SONDAGE SORTANT des issues, et non par webhook
# GitHub : n8n écoute sur 127.0.0.1, donc GitHub ne peut rien lui livrer — et
# exposer n8n publiquement est exclu. Le sondage n'ouvre aucun port.
REPO = "AtmanTest/jobhunt"
LABEL_DEMANDE = "agent:go"
LABEL_EN_COURS = "agent:running"
LABEL_TRAITEE = "agent:done"
INTERVALLE_MINUTES = 5


def lire_prompts() -> dict[str, str]:
    """Lit les prompts de rôle depuis le dépôt (source de vérité)."""
    manquants = [f for f in ROLES.values() if not (PROMPTS / f).is_file()]
    if manquants:
        raise SystemExit(f"prompts manquants : {', '.join(manquants)}")
    return {cle: (PROMPTS / f).read_text(encoding="utf-8") for cle, f in ROLES.items()}


def noeud_llm(nom: str, role: str, entree_js: str, x: int, y: int) -> dict:
    """Nœud d'appel LLM : prompt de rôle en `system` (stable), artefact en `user`."""
    corps = (
        "={{ JSON.stringify({"
        f" model: '{MODELE[role]}', stream: false, max_tokens: {MAX_TOKENS[role]},"
        " messages: ["
        "  { role: 'system', content: $('Préparer').first().json.roles." + role + " },"
        "  { role: 'user', content: " + entree_js + " }"
        " ] }) }}"
    )
    return {
        "parameters": {
            "method": "POST",
            "url": HERMES_URL,
            "options": {"timeout": 900000},
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": corps,
        },
        "id": f"llm-{role}",
        "name": nom,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [x, y],
        "credentials": CRED_HERMES,
    }


def noeud_github(nom: str, methode: str, url: str, corps: str | None, x: int, y: int) -> dict:
    """Appel REST GitHub avec le credential GitHub existant (aucun jeton en clair)."""
    params: dict = {
        "method": methode,
        "url": url,
        "options": {"timeout": 120000},
        "authentication": "predefinedCredentialType",
        "nodeCredentialType": "githubApi",
    }
    if corps is not None:
        params.update({"sendBody": True, "specifyBody": "json", "jsonBody": corps})
    return {
        "parameters": params,
        "id": "gh-" + re.sub(r"\W+", "-", nom).lower(),
        "name": nom,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [x, y],
        "credentials": CRED_GITHUB,
    }


def noeud_code(nom: str, code: str, x: int, y: int, mode: str = "runOnceForAllItems") -> dict:
    return {
        "parameters": {"mode": mode, "jsCode": code},
        "id": "code-" + re.sub(r"\W+", "-", nom).lower(),
        "name": nom,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [x, y],
    }


def noeud_si(nom: str, conditions: dict, x: int, y: int) -> dict:
    return {
        "parameters": {"conditions": conditions, "options": {}},
        "id": "if-" + re.sub(r"\W+", "-", nom).lower(),
        "name": nom,
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [x, y],
    }


def noeud_pg(nom: str, requete: str, x: int, y: int) -> dict:
    return {
        "parameters": {"operation": "executeQuery", "query": requete, "options": {}},
        "id": "pg-" + re.sub(r"\W+", "-", nom).lower(),
        "name": nom,
        "type": "n8n-nodes-base.postgres",
        "typeVersion": 2.4,
        "position": [x, y],
        "credentials": CRED_PG,
    }


# --- code embarqué ------------------------------------------------------------

CODE_PREPARER = """// Prépare le contexte du run.
// Le prompt de rôle (message system) est IDENTIQUE d'un run à l'autre : c'est la
// partie stable, placée en tête pour être servie depuis le cache du fournisseur.
const evt = $json.body ?? $json;
const issue = evt.issue ?? {};
const action = String(evt.action ?? '');
const label = String((evt.label && evt.label.name) || '');
const labels = (issue.labels || []).map(l => (typeof l === 'string' ? l : l.name));

const declencheur = ['opened', 'edited', 'reopened', 'labeled'].includes(action);
const autorise = label === 'agent:go' || labels.includes('agent:go');

if (!declencheur || !autorise) {
  return [{ json: { ignore: true, raison: `action=${action} label=${label}` } }];
}
if (!evt.repository || !issue.number) {
  return [{ json: { ignore: true, raison: 'charge utile GitHub incomplète' } }];
}

const repo = evt.repository.full_name;
const numero = issue.number;
const titre = String(issue.title || '').trim();
const corps = String(issue.body || '').trim();

return [{ json: {
  ignore: false,
  runId: `${repo}#${numero}-${Date.now()}`,
  repo, numero, titre,
  issue_url: issue.html_url,
  // Seul le ticket est transmis : pas d'historique, pas de contexte parasite.
  issue_text: `# ${titre}\\n\\n${corps}`,
  roles: __ROLES__,
} }];
"""

CODE_SELECTION = """// Choisit LA prochaine issue à traiter, par sondage sortant.
// Sont écartées : les pull requests (l'API issues les renvoie aussi) et les
// issues déjà prises ou terminées — le cycle de vie est porté par les étiquettes.
const liste = Array.isArray($json) ? $json : ($json.issues || $json.items || []);
const issues = liste.filter(i => i && !i.pull_request);

const aTraiter = issues.filter(i => {
  const noms = (i.labels || []).map(l => (typeof l === 'string' ? l : l.name));
  return noms.includes('__DEMANDE__')
      && !noms.includes('__EN_COURS__')
      && !noms.includes('__TRAITEE__');
});

if (!aTraiter.length) {
  return [{ json: { ignore: true, raison: 'aucune issue étiquetée __DEMANDE__ à traiter' } }];
}

const issue = aTraiter[0];
// Forme normalisée identique à celle d'un webhook GitHub : le reste de la
// chaîne ne sait pas d'où vient le ticket.
return [{ json: {
  action: 'labeled',
  label: { name: '__DEMANDE__' },
  issue,
  repository: { full_name: '__REPO__' },
} }];
"""


CODE_PREPARER_ECRITURE = """// Transforme la sortie de l'agent Dev en écritures de fichiers réelles.
// L'agent Dev doit répondre en JSON : {branch, commit_message, files:[{path, content}]}.
$('Dev — fichiers').first().json;
const ctx = $('Préparer').first().json;
const brut = $('Dev — fichiers').first().json.choices[0].message.content;

function extraireJson(txt) {
  const bloc = txt.match(/```(?:json)?\\s*([\\s\\S]*?)```/);
  const candidat = bloc ? bloc[1] : txt;
  const debut = candidat.indexOf('{');
  const fin = candidat.lastIndexOf('}');
  if (debut === -1 || fin === -1) throw new Error('réponse Dev sans JSON exploitable');
  return JSON.parse(candidat.slice(debut, fin + 1));
}

const dev = extraireJson(brut);
const slug = (ctx.titre || 'issue').toLowerCase()
  .normalize('NFD').replace(/[\\u0300-\\u036f]/g, '')
  .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40) || 'issue';
const branche = dev.branch || `agent/issue-${ctx.numero}-${slug}`;

// Les artefacts de spécification sont versionnés avec le code : le ticket
// devient un dossier de specs, pas un prompt jetable.
const artefacts = [
  { path: `specs/${ctx.numero}-${slug}/spec.md`,
    content: `# ${ctx.titre}\\n\\n_Source : ${ctx.issue_url}_\\n\\n## Spécification (agent PO)\\n\\n${$('PO — critères').first().json.choices[0].message.content}\\n` },
  { path: `specs/${ctx.numero}-${slug}/review.md`,
    content: `# Revue de spécification\\n\\n${$('Spec Review').first().json.choices[0].message.content}\\n` },
  { path: `specs/${ctx.numero}-${slug}/plan.md`,
    content: `# Plan technique\\n\\n${$('Architecte — plan').first().json.choices[0].message.content}\\n\\n## Cas de test (agent QA)\\n\\n${$('QA — cas de test').first().json.choices[0].message.content}\\n` },
];

const fichiers = [...(dev.files || []), ...artefacts];
if (!fichiers.length) throw new Error("l'agent Dev n'a produit aucun fichier");

return [{
  json: {
    ...ctx,
    branche,
    commit_message: dev.commit_message || `feat: ${ctx.titre}`,
    fichiers,
    // main est lu à l'exécution : la branche part toujours de l'état courant.
    sha_base: $('Référence main').first().json.object.sha,
  },
}];
"""

CODE_CHEMINS = """// Liste des chemins existants du dépôt — NOMS SEULS, jamais le contenu.
// Objectif : que l'agent Dev sache où il écrit sans qu'on lui envoie le code
// (envoyer l'arborescence complète coûterait des milliers de tokens par run).
const arbre = ($json.tree || []).filter(e => e.type === 'blob');
const plafond = 400;
const chemins = arbre.slice(0, plafond).map(e => e.path).join('\\n');
return [{ json: {
  nb_fichiers: arbre.length,
  tronque: arbre.length > plafond,
  chemins: tronque ? chemins + '\\n(…)' : chemins,
} }];
"""


CODE_NORMALISER = """// Un item par fichier : l'écriture se fait par appel unitaire à l'API Contents.
const d = $json;
return d.fichiers.map(f => ({ json: {
  path: f.path,
  contenu_base64: Buffer.from(String(f.content || ''), 'utf8').toString('base64'),
  branche: d.branche,
  repo: d.repo,
  commit_message: d.commit_message,
} }));
"""

CODE_ANALYSER_CI = """// Verdict de la CI, rattaché au commit RÉELLEMENT produit (et non au dernier
// run du dépôt, ce que faisait la version précédente : le verdict ne portait
// alors sur rien).
const runs = Array.isArray($json.workflow_runs) ? $json.workflow_runs : [];
const ctx = $('Préparer').first().json;
const sha = $('Lire le commit').first().json.object.sha;
const tentative = (ctx.tentative || 0) + 1;

const run = runs.find(r => r.head_sha === sha) || null;
const statut = run ? run.status : 'absent';
const conclusion = run ? (run.conclusion || 'en_cours') : 'absent';

let decision = 'attendre';
if (statut === 'completed') {
  if (conclusion === 'success') decision = 'succes';
  else if (tentative < __MAX__) decision = 'corriger';
  else decision = 'abandon';
}

return [{ json: {
  ...ctx,
  sha,
  run_url: run ? run.html_url : null,
  statut, conclusion, tentative, decision,
} }];
"""

CODE_RAPPORT = """// Rapport de livraison, posté en commentaire de la PR.
const ctx = $('Préparer').first().json;
const ci = $('Analyser la CI').first().json;
const verdict = $('QA Review').first().json.choices[0].message.content || '(vide)';
const sha = ci.sha || '';

const md = [
  '# Rapport de livraison',
  '',
  `- Ticket : ${ctx.issue_url}`,
  `- Branche : \\`${$('Préparer l\\'écriture').first().json.branche}\\``,
  `- Commit testé : \\`${sha.slice(0, 7)}\\``,
  `- CI : ${ci.conclusion} (${ci.run_url || 'sans run'})`,
  `- Tentatives de correction : ${ci.tentative - 1}`,
  `- Horodatage : ${new Date().toLocaleString('fr-FR')}`,
  '',
  '## Revue QA', '', verdict, '',
  '## Traçabilité', '',
  '| Étape | Artefact |',
  '|---|---|',
  `| PO — critères | \\`specs/${ctx.numero}-*/spec.md\\` |`,
  `| Spec Review | \\`specs/${ctx.numero}-*/review.md\\` |`,
  '| Architecte + QA | `plan.md` |',
].join('\\n');

return [{ json: { ...ctx, corps_rapport: md } }];
"""


def construire(roles: dict[str, str]) -> dict:
    """Assemble le workflow complet."""
    def roles_js() -> str:
        return json.dumps(roles, ensure_ascii=False)

    nodes = [
        {
            "parameters": {
                "rule": {"interval": [{"field": "minutes",
                                       "minutesInterval": INTERVALLE_MINUTES}]},
            },
            "id": "tr-horaire",
            "name": "Déclencheur — sondage",
            "type": "n8n-nodes-base.scheduleTrigger",
            "typeVersion": 1.2,
            "position": [-2200, 180],
        },
        noeud_github(
            "Lire les issues",
            "GET",
            f"https://api.github.com/repos/{REPO}/issues?labels={LABEL_DEMANDE}"
            "&state=open&per_page=20",
            None, -2000, 180,
        ),
        noeud_code(
            "Sélectionner l'issue",
            CODE_SELECTION.replace("__DEMANDE__", LABEL_DEMANDE)
                         .replace("__EN_COURS__", LABEL_EN_COURS)
                         .replace("__TRAITEE__", LABEL_TRAITEE)
                         .replace("__REPO__", REPO),
            -1800, 180,
        ),
        noeud_code(
            "Préparer",
            CODE_PREPARER.replace("__ROLES__", roles_js()),
            -1400, 300,
        ),
        noeud_si("Ticket éligible ?", {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
            "conditions": [{
                "id": "c1",
                "leftValue": "={{ $json.ignore }}",
                "rightValue": False,
                "operator": {"type": "boolean", "operation": "equals"},
            }],
            "combinator": "and",
        }, -1200, 300),
        noeud_pg(
            "Journal — début",
            "insert into public.pipeline_events (workflow, event, payload) "
            "values ('wf2-agents','run_demarre',"
            " jsonb_build_object('run', '{{ $json.runId }}', 'repo', '{{ $json.repo }}',"
            " 'issue', {{ $json.numero }}, 'titre', '{{ $('Préparer').first().json.titre }}'));",
            -1000, 300,
        ),
        noeud_llm("PO — critères", "PO",
                  "$('Préparer').first().json.issue_text", -800, 300),
        noeud_llm("Spec Review", "SpecReview",
                  "$('PO — critères').first().json.choices[0].message.content", -600, 300),
        noeud_si("Porte — Spec Review", {
            "options": {"caseSensitive": False, "leftValue": "", "typeValidation": "loose", "version": 2},
            "conditions": [{
                "id": "c2",
                "leftValue": "={{ $json.choices[0].message.content }}",
                "rightValue": "NO-GO",
                "operator": {"type": "string", "operation": "notContains"},
            }],
            "combinator": "and",
        }, -400, 300),
        noeud_llm("Architecte — plan", "Architecte",
                  "$('PO — critères').first().json.choices[0].message.content"
                  " + '\\n\\n## Revue de la spécification\\n'"
                  " + $('Spec Review').first().json.choices[0].message.content", -200, 300),
        noeud_llm("QA — cas de test", "QA",
                  "$('Architecte — plan').first().json.choices[0].message.content", 0, 300),
        noeud_github(
            "Arborescence",
            "GET",
            "https://api.github.com/repos/{{ $('Préparer').first().json.repo }}"
            "/git/trees/main?recursive=1",
            None, 100, 480,
        ),
        noeud_code("Chemins du dépôt", CODE_CHEMINS, 150, 480),
        noeud_llm("Dev — fichiers", "Dev",
                  "$('QA — cas de test').first().json.choices[0].message.content"
                  " + '\\n\\n## Ticket\\n' + $('Préparer').first().json.issue_text"
                  " + '\\n\\n## Chemins existants du dépôt (n\'écris que ce qui manque)\\n'"
                  " + $('Chemins du dépôt').first().json.chemins", 200, 300),
        noeud_code("Préparer l'écriture", CODE_PREPARER_ECRITURE, 400, 300),
        noeud_github("Référence main", "GET",
                     "https://api.github.com/repos/{{ $json.repo }}/git/ref/heads/main",
                     None, 600, 120),
        noeud_github("Créer la branche", "POST",
                     "https://api.github.com/repos/{{ $('Préparer').first().json.repo }}/git/refs",
                     "={{ JSON.stringify({ ref: 'refs/heads/' + $json.branche,"
                     " sha: $json.sha_base }) }}", 800, 300),
        noeud_code("Normaliser les écritures", CODE_NORMALISER, 1000, 300),
        noeud_github("Écrire les fichiers", "PUT",
                     "https://api.github.com/repos/{{ $json.repo }}/contents/{{ $json.path }}",
                     "={{ JSON.stringify({ message: $json.commit_message,"
                     " content: $json.contenu_base64, branch: $json.branche }) }}", 1200, 300),
        noeud_github("Lire le commit", "GET",
                     "https://api.github.com/repos/{{ $('Préparer').first().json.repo }}"
                     "/git/ref/heads/{{ $('Préparer l\\'écriture').first().json.branche }}",
                     None, 1400, 300),
        noeud_github("Ouvrir la PR", "POST",
                     "https://api.github.com/repos/{{ $('Préparer').first().json.repo }}/pulls",
                     "={{ JSON.stringify({ title: $('Préparer').first().json.titre,"
                     " head: $('Préparer l\\'écriture').first().json.branche, base: 'main',"
                     " body: 'Chaîne d\\'agents — artefacts dans specs/." 
                     " Ticket : ' + $('Préparer').first().json.issue_url }) }}", 1600, 300),
        noeud_github("CI — statut", "GET",
                     "https://api.github.com/repos/{{ $('Préparer').first().json.repo }}"
                     "/actions/runs?head_sha={{ $('Lire le commit').first().json.object.sha }}",
                     None, 1800, 300),
        noeud_code("Analyser la CI",
                   CODE_ANALYSER_CI.replace("__MAX__", str(MAX_TENTATIVES)), 2000, 300),
        noeud_si("CI terminée ?", {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
            "conditions": [{
                "id": "c3",
                "leftValue": "={{ $json.decision }}",
                "rightValue": "attendre",
                "operator": {"type": "string", "operation": "notEquals"},
            }],
            "combinator": "and",
        }, 2200, 300),
        noeud_si("Résultat ?", {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
            "conditions": [{
                "id": "c4",
                "leftValue": "={{ $json.decision }}",
                "rightValue": "succes",
                "operator": {"type": "string", "operation": "equals"},
            }],
            "combinator": "and",
        }, 2400, 300),
        noeud_llm("Fix", "Fix",
                  "$('Analyser la CI').first().json.conclusion"
                  " + '\\n\\n## Cas de test\\n'"
                  " + $('QA — cas de test').first().json.choices[0].message.content", 2400, 520),
        noeud_llm("QA Review", "QAReview",
                  "$('Analyser la CI').first().json.conclusion"
                  " + '\\n\\n## Critères\\n'"
                  " + $('PO — critères').first().json.choices[0].message.content", 2600, 300),
        noeud_code("Rapport", CODE_RAPPORT, 2800, 300),
        noeud_github("Poster le rapport", "POST",
                     "https://api.github.com/repos/{{ $json.repo }}/issues/{{ $json.numero }}/comments",
                     "={{ JSON.stringify({ body: $json.corps_rapport }) }}", 3000, 300),
        noeud_pg(
            "Journal — verdict",
            "insert into public.gates (run_id, porte, verdict, motif, empreinte_tested, empreinte_head) "
            "values ('{{ $('Préparer').first().json.runId }}', 'ci',"
            " '{{ $('Analyser la CI').first().json.conclusion }}',"
            " '{{ $('Analyser la CI').first().json.decision }}',"
            " '{{ $('Analyser la CI').first().json.sha }}',"
            " '{{ $('Analyser la CI').first().json.sha }}');",
            3200, 300,
        ),
        noeud_github(
            "Marquer traitée",
            "POST",
            "https://api.github.com/repos/{{ $('Préparer').first().json.repo }}"
            "/issues/{{ $('Préparer').first().json.numero }}/labels",
            "={{ JSON.stringify({ labels: ['" + LABEL_TRAITEE + "'] }) }}",
            3400, 300,
        ),
        noeud_github(
            "Retirer la demande",
            "DELETE",
            "https://api.github.com/repos/{{ $('Préparer').first().json.repo }}"
            "/issues/{{ $('Préparer').first().json.numero }}/labels/" + LABEL_DEMANDE,
            None, 3600, 300,
        ),
        {
            "parameters": {},
            "id": "noop-fin",
            "name": "Fin",
            "type": "n8n-nodes-base.noOp",
            "typeVersion": 1,
            "position": [3800, 300],
        },
    ]

    # --- connexions ---------------------------------------------------------
    def lien(*noms):
        return {"main": [[{"node": n, "type": "main", "index": 0}] for n in noms]}

    connections = {
        "Déclencheur — sondage": lien("Lire les issues"),
        "Lire les issues": lien("Sélectionner l'issue"),
        "Sélectionner l'issue": lien("Préparer"),
        "Préparer": lien("Ticket éligible ?"),
        "Ticket éligible ?": {"main": [[{"node": "Journal — début", "type": "main", "index": 0}], []]},
        "Journal — début": lien("PO — critères"),
        "PO — critères": lien("Spec Review"),
        "Spec Review": lien("Porte — Spec Review"),
        "Porte — Spec Review": {
            "main": [
                [{"node": "Architecte — plan", "type": "main", "index": 0}],
                [{"node": "Fin", "type": "main", "index": 0}],
            ]
        },
        "Architecte — plan": lien("QA — cas de test"),
        "QA — cas de test": lien("Arborescence"),
        "Arborescence": lien("Chemins du dépôt"),
        "Chemins du dépôt": lien("Dev — fichiers"),
        "Dev — fichiers": lien("Préparer l'écriture"),
        "Préparer l'écriture": lien("Référence main"),
        "Référence main": lien("Créer la branche"),
        "Créer la branche": lien("Normaliser les écritures"),
        "Normaliser les écritures": lien("Écrire les fichiers"),
        "Écrire les fichiers": lien("Lire le commit"),
        "Lire le commit": lien("Ouvrir la PR"),
        "Ouvrir la PR": lien("CI — statut"),
        "CI — statut": lien("Analyser la CI"),
        "Analyser la CI": lien("CI terminée ?"),
        "CI terminée ?": {"main": [[{"node": "Résultat ?", "type": "main", "index": 0}], []]},
        "Résultat ?": {
            "main": [
                [{"node": "QA Review", "type": "main", "index": 0}],
                [{"node": "Fix", "type": "main", "index": 0}],
            ]
        },
        "Fix": {"main": [[{"node": "Préparer l'écriture", "type": "main", "index": 0}]]},
        "QA Review": lien("Rapport"),
        "Rapport": lien("Poster le rapport"),
        "Poster le rapport": lien("Journal — verdict"),
        "Journal — verdict": lien("Marquer traitée"),
        "Marquer traitée": lien("Retirer la demande"),
        "Retirer la demande": lien("Fin"),
    }

    return {
        "id": "wf2agentsjobhunt",
        "name": "JobHunt — WF2 Chaîne d'agents (issue → PR)",
        "active": False,
        "settings": {"executionOrder": "v1"},
        "nodes": nodes,
        "connections": connections,
        "meta": {
            "généré par": "workflows/build_wf2.py",
            "prompts": "lus depuis prompts/*.md — ne pas éditer ce JSON à la main",
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="vérifie que le JSON versionné correspond aux prompts")
    args = ap.parse_args()

    roles = lire_prompts()
    workflow = construire(roles)
    contenu = json.dumps(workflow, indent=2, ensure_ascii=False) + "\n"

    if args.check:
        if not SORTIE.is_file():
            print("wf2_agents.json absent : lancer build_wf2.py", file=sys.stderr)
            return 1
        if SORTIE.read_text(encoding="utf-8") != contenu:
            print("wf2_agents.json a dérivé des prompts : relancer build_wf2.py",
                  file=sys.stderr)
            return 1
        print("wf2_agents.json à jour avec prompts/*.md")
        return 0

    SORTIE.write_text(contenu, encoding="utf-8")
    print(f"{SORTIE.relative_to(RACINE)} écrit — {len(workflow['nodes'])} nœuds, "
          f"{len(workflow['connections'])} connexions, {len(roles)} prompts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
