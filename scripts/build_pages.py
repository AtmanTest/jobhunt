#!/usr/bin/env python3
"""Construit la version statique publiable sur GitHub Pages.

Usage : python3 scripts/build_pages.py [dossier_de_sortie]

Sortie par défaut : /tmp/jobhunt-pages

Ce qui est publié :
  - la vitrine du PoC ISTQB CT-AI (métriques, relations métamorphiques, défauts corrigés)
  - la chaîne de livraison virtuelle (processus complet, campagnes réellement exécutées)
  - le dossier de portes (les 6 documents de docs/qa-ct-ai/ convertis en pages HTML)

Les pages sont rendues par le vrai moteur (Flask + Jinja) puis figées : les données
affichées (métriques, résultats de campagnes, anomalies) sont calculées par exécution
réelle des tests, pas saisies à la main. Sur une page statique, la ré-exécution à la
demande n'est pas possible : les exemples du banc d'essai sont donc précalculés par le
même moteur, et la page le dit explicitement.
"""
from __future__ import annotations

import json
import os
import re
import re
import shutil
import sys
from datetime import datetime

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

SORTIE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/jobhunt-pages"

# ---------------------------------------------------------------------------
# 1. Données : elles viennent du moteur, jamais d'une saisie manuelle
# ---------------------------------------------------------------------------
import virtual_delivery as vd  # noqa: E402
from matcher import analyze_tjm, match_job_to_cv  # noqa: E402

with open(os.path.join(RACINE, "docs", "qa-ct-ai", "evidence.json"), encoding="utf-8") as fh:
    EVIDENCE = json.load(fh)


def _scenario_public():
    """Le scénario complet, tel que le sert l'API /poc-delivery/api/scenario."""
    scenario = vd.scenario_complet()

    def bloc(campagne, anomalies, criteres=None):
        d = {"campagne": campagne, "anomalies": anomalies}
        if criteres is not None:
            d["criteres_sortie"] = criteres
        return d

    verts_v1 = {r["cas"] for r in scenario["v1_campagne"]["resultats"] if r["statut"] == "réussi"}
    rouges_v2 = set(scenario["v2_regression"]["synthese"]["ids_en_echec"])

    return {
        "demande": vd.DEMANDE_METIER,
        "user_stories": vd.USER_STORIES,
        "etapes": vd.ETAPES,
        "versions": vd.VERSIONS,
        "cas": [{k: v for k, v in c.items() if k not in ("fonction", "attendu_valeur")}
                for c in vd.CAS_DE_TEST],
        "tracabilite": vd.tracabilite(),
        "campagnes": {
            "v1_execution": bloc(scenario["v1_campagne"], scenario["v1_anomalies"],
                                 scenario["v1_verdict"]),
            "v2_confirmation": bloc(scenario["v2_confirmation"],
                                    vd.rapports_anomalie(scenario["v2_confirmation"]["resultats"])),
            "v2_regression": bloc(scenario["v2_regression"], scenario["v2_anomalies"],
                                  scenario["v2_verdict"]),
            "v3_confirmation": bloc(scenario["v3_confirmation"],
                                    vd.rapports_anomalie(scenario["v3_confirmation"]["resultats"])),
            "v3_regression": bloc(scenario["v3_regression"], scenario["v3_anomalies"],
                                  scenario["v3_verdict"]),
            "regressions_nouvelles": sorted(verts_v1 & rouges_v2),
        },
        "genere_le": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    }


SCENARIO = _scenario_public()

# ---------------------------------------------------------------------------
# 2. Exemples précalculés pour le banc d'essai de la vitrine CT-AI
# ---------------------------------------------------------------------------
GABARIT_VITRINE = open(os.path.join(RACINE, "templates", "poc_ct_ai.html"), encoding="utf-8").read()


def _defaut_formulaire():
    """Valeurs par défaut du formulaire, lues dans le gabarit (jamais recopiées à la main)."""
    def champ(ident):
        m = re.search(r'id="' + ident + r'"[^>]*value="([^"]*)"', GABARIT_VITRINE)
        return m.group(1) if m else ""

    def option(ident):
        bloc = re.search(r'id="' + ident + r'"[^>]*>(.*?)</select>', GABARIT_VITRINE, re.S)
        return re.search(r'value="([^"]*)"', bloc.group(1)).group(1) if bloc else ""

    desc = re.search(r'id="d-desc">(.*?)</textarea>', GABARIT_VITRINE, re.S)
    return {
        "title": champ("d-title"), "tags": champ("d-tags"), "salary": champ("d-salary"),
        "location": champ("d-location"), "remote_type": option("d-remote"),
        "freelance_status": option("d-status"),
        "description": desc.group(1) if desc else "",
    }


DEFAUT = _defaut_formulaire()
assert DEFAUT["title"] and DEFAUT["description"], "valeurs par défaut du formulaire introuvables"


def _exemple_du_bouton(marqueur):
    """Reconstruit une offre d'exemple à partir du bloc chargerExemple() du gabarit."""
    bloc = GABARIT_VITRINE.split(marqueur, 1)[1].split("}", 1)[0]

    def valeur(ident, attr="value"):
        motif = "getElementById\\('" + re.escape(ident) + "'\\)\\." + attr + ' = "?([^";]*)"?'
        trouve = re.search(motif, bloc)
        return trouve.group(1) if trouve else ""
    return {
        "title": valeur("d-title"), "tags": valeur("d-tags"), "salary": valeur("d-salary"),
        "description": valeur("d-desc"), "location": DEFAUT["location"],
        "remote_type": valeur("d-remote"), "freelance_status": valeur("d-status"),
    }


EXEMPLES = [
    {"nom": "Offre QA freelance (état par défaut du formulaire)", **DEFAUT},
    {"nom": "Même offre écrite autrement (majuscules, statut en minuscules)", "derive": True,
     **{**DEFAUT, "title": DEFAUT["title"].upper(), "remote_type": "Remote",
        "freelance_status": "validée"}},
    {"nom": "Offre hors sujet (piège du mot « capital »)", **_exemple_du_bouton("'hors-sujet'")},
    {"nom": "Offre QA Lead (full remote, autre profil)", **_exemple_du_bouton("'qa'")},
]
for _ex in EXEMPLES:
    if _ex.get("derive"):
        continue
    for _champ, _valeur in _ex.items():
        if _champ in ("nom", "derive") or not isinstance(_valeur, str) or len(_valeur) <= 12:
            continue
        assert _valeur[:24] in GABARIT_VITRINE, f"exemple désynchronisé du gabarit : {_valeur[:40]!r}"


def _cle(offre):
    champs = ["title", "tags", "salary", "location", "remote_type", "freelance_status", "description"]
    return "|".join((offre.get(c) or "") for c in champs)


def _controler(offre):
    """Même contrôle d'invariance que l'API : rejoue l'offre écrite autrement."""
    score, competences = match_job_to_cv(dict(offre))
    variantes = [
        ("Titre et description en MAJUSCULES",
         {**offre, "title": offre["title"].upper(), "description": offre["description"].upper()}),
        ("Accents retirés", {**offre, "description": offre["description"]}),
        ("Espaces ajoutés en bord de champs",
         {**offre, "title": "  " + offre["title"] + "   ", "description": "  " + offre["description"] + "  "}),
        ("Ponctuation ajoutée au titre", {**offre, "title": offre["title"] + " !!!"}),
        ("Statut freelance en minuscules", {**offre, "freelance_status": offre["freelance_status"].lower()}),
    ]
    controle = []
    for nom, variante in variantes:
        score_variante, _ = match_job_to_cv(variante)
        controle.append({"nom": nom, "score": score_variante, "identique": score_variante == score})
    return {
        "score": score, "competences": competences, "tjm": analyze_tjm(dict(offre)),
        "salaire_source": offre.get("salary", ""), "pertinent": score >= 40, "seuil": 40,
        "controle": controle, "invariance_ok": all(c["identique"] for c in controle),
    }


SCORES = {}
for exemple in EXEMPLES:
    SCORES[_cle(exemple)] = _controler(exemple)

# ---------------------------------------------------------------------------
# 3. Rendu des pages par le vrai moteur, puis figeage
# ---------------------------------------------------------------------------
from app import app  # noqa: E402  (import après les données : l'app lit ses env au démarrage)

client = app.test_client()


LIENS_STATIQUES = {
    'href="/"': 'href="index.html"',
    'href="/poc-ct-ai"': 'href="vitrine-ct-ai.html"',
    'href="/poc-delivery"': 'href="chaine-de-livraison.html"',
    'href="/cycle-de-vie"': 'href="cycle-de-vie.html"',
    'href="/qa"': 'href="index.html"',
    'href="/about"': 'href="index.html"',
}


def _page(route):
    """Rend une route avec le vrai moteur, puis réécrit les liens pour un site statique."""
    reponse = client.get(route)
    assert reponse.status_code == 200, f"{route} a renvoyé {reponse.status_code}"
    html = reponse.get_data(as_text=True)
    for avant, apres in LIENS_STATIQUES.items():
        html = html.replace(avant, apres)
    return html


ENTETE = """<header class="entete">
  <div class="entete-in">
    <a class="marque" href="index.html"><span class="orbe"></span>
      <span class="pile"><span>JobHunt</span><small>QA · Démonstrations</small></span></a>
    <nav class="nav">
      <a{h1} href="cycle-de-vie.html">Cycle de vie</a>
      <a{h2} href="chaine-de-livraison.html">Chaîne de livraison</a>
      <a{h3} href="vitrine-ct-ai.html">Test d'IA</a>
      <a{h4} href="index.html">Sommaire</a>
    </nav>
  </div>
  <div class="jauge"></div>
</header>"""

PIED = """<footer class="pied"><div class="pied-in">
  <span>JobHunt · démonstrations de test logiciel et de test d'IA</span>
  <span style="margin-left:auto;">Chiffres issus d'exécutions réelles · dépôt privé, code présenté sur demande</span>
</div></footer>"""


def _chrome(html, actif=0):
    """Applique l'enveloppe visuelle commune à une page rendue par l'application."""
    html = re.sub(r'<link rel="stylesheet" href="/?static/(?:theme|v3)\.css[^"]*">\s*', "", html)
    marques = {i: (' class="actif"' if i == actif else "") for i in range(1, 5)}
    html = re.sub(r'<header class="header">.*?</header>', ENTETE.format(**{
        f"h{i}": marques[i] for i in range(1, 5)}), html, flags=re.S)
    if 'class="ciel"' not in html:
        html = re.sub(r"<body([^>]*)>", r'<body\1>\n<div class="ciel"></div>', html, count=1)
    if "static/site.css" not in html:
        html = html.replace("</head>", '<link rel="stylesheet" href="static/site.css">\n</head>')
    if "static/site.js" not in html:
        html = html.replace("</body>", PIED + '\n<script src="static/site.js" defer></script>\n</body>')
    return html


os.makedirs(os.path.join(SORTIE, "static"), exist_ok=True)
for asset in ("theme.css", "site.css", "site.js"):
    source = os.path.join(RACINE, "static", asset)
    if os.path.exists(source):
        shutil.copy2(source, os.path.join(SORTIE, "static", asset))

# --- chaîne de livraison : le scénario est injecté à la place de l'appel réseau
livraison = _page("/poc-delivery")
livraison = livraison.replace(
    "  const rep = await fetch('/poc-delivery/api/scenario');\n  S = await rep.json();",
    "  S = window.__SCENARIO__;")
livraison = livraison.replace(
    "async function charger() {",
    "const __SCENARIO_JSON__ = " + json.dumps(SCENARIO, ensure_ascii=False) + ";\n"
    "window.__SCENARIO__ = __SCENARIO_JSON__;\n\nasync function charger() {")
livraison = livraison.replace(
    "'Scénario exécuté le ' + S.genere_le",
    "'Démonstration statique (GitHub Pages) — scénario exécuté le ' + S.genere_le")
html_livraison = _chrome(livraison, actif=2)

# --- vitrine CT-AI : les évaluations d'exemple sont précalculées
vitrine = _page("/poc-ct-ai")
vitrine = vitrine.replace(
    "  const rep = await fetch('/poc-ct-ai/api/score', {\n"
    "    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)\n"
    "  });\n  const d = await rep.json();",
    "  const cle = [payload.title, payload.tags, payload.salary, payload.location, payload.remote_type,\n"
    "               payload.freelance_status, payload.description].map(v => v || '').join('|');\n"
    "  const d = window.__SCORES__[cle];\n"
    "  if (!d) {\n"
    "    alert(\"Page statique : le calcul à la demande nécessite le serveur.\\n\"\n"
    "      + \"Choisissez un des exemples proposés : ils sont calculés par le même moteur.\");\n"
    "    return;\n"
    "  }")
vitrine = vitrine.replace(
    "<script>\nasync function noter() {",
    "<script>\nwindow.__SCORES__ = " + json.dumps(SCORES, ensure_ascii=False) + ";\n\nasync function noter() {")
vitrine = vitrine.replace(
    "Corpus d'évaluation : ",
    "Démonstration statique (GitHub Pages) : les chiffres ci-dessous proviennent d'une exécution réelle du "
    "moteur et de la suite de tests. Corpus d'évaluation : ")
html_vitrine = _chrome(vitrine, actif=3)

cycle = _page("/cycle-de-vie")
with open(os.path.join(SORTIE, "vitrine-ct-ai.html"), "w", encoding="utf-8") as fh:
    fh.write(html_vitrine)
with open(os.path.join(SORTIE, "cycle-de-vie.html"), "w", encoding="utf-8") as fh:
    fh.write(cycle)
with open(os.path.join(SORTIE, "chaine-de-livraison.html"), "w", encoding="utf-8") as fh:
    fh.write(html_livraison)

# ---------------------------------------------------------------------------
# 4. Le dossier de portes en pages HTML
# ---------------------------------------------------------------------------
try:
    import markdown as md
    _md = lambda t: md.markdown(t, extensions=["tables", "fenced_code", "toc"])  # noqa: E731
except ImportError:  # pragma: no cover
    _md = lambda t: "<pre>" + t.replace("<", "&lt;") + "</pre>"  # noqa: E731

ENTETE_INDEX = ENTETE.format(h1=' class="actif"', h2="", h3="", h4="")
ENTETE_DOC = ENTETE.format(h1="", h2="", h3="", h4=' class="actif"')

GABARIT = """<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{titre} — JobHunt</title>
<link rel="stylesheet" href="static/site.css">
</head><body>
<div class="ciel"></div>
{entete}
<div class="page">
  <div class="oeil">Portes de qualité · la démarche écrite</div>
  <h1>{titre}</h1>
  <div class="panneau doc" style="margin-top:1.2rem;">{corps}</div>
  <p style="margin-top:1.6rem;"><a href="index.html">← Retour au sommaire</a></p>
</div>
{pied}
<script src="static/site.js" defer></script>
</body></html>"""

DOCS = [
    ("01-cadrage-risque-ia.md", "Porte 1 — Cadrage du risque IA"),
    ("02-qualite-donnees.md", "Porte 2 — Qualité des données"),
    ("03-metriques-seuils.md", "Porte 3 — Métriques et seuils verrouillés"),
    ("04-plan-de-test.md", "Porte 4 — Plan de test"),
    ("05-techniques.md", "Porte 5 — Techniques appliquées"),
    ("06-journal-aide-ia.md", "Porte 6 — Journal d'usage de l'IA"),
]
index_docs = []
for nom, titre in DOCS:
    chemin = os.path.join(RACINE, "docs", "qa-ct-ai", nom)
    if not os.path.exists(chemin):
        continue
    corps = _md(open(chemin, encoding="utf-8").read())
    cible = nom.replace(".md", ".html")
    with open(os.path.join(SORTIE, cible), "w", encoding="utf-8") as fh:
        fh.write(GABARIT.format(titre=titre, corps=corps, entete=ENTETE_DOC,
                              pied=PIED))
    index_docs.append((cible, titre))

# ---------------------------------------------------------------------------
# 5. Page d'accueil
# ---------------------------------------------------------------------------
t = EVIDENCE["tests"]
m = EVIDENCE["metriques"]
s = SCENARIO
try:
    with open(os.path.join(RACINE, "docs", "qa-ct-ai", "lifecycle.json"), encoding="utf-8") as fh:
        LIFE = json.load(fh)
except (OSError, ValueError):
    LIFE = {"playwright": {"nb_passes": 0, "nb_scenarios": 0}, "historique": {}, "campagnes": {}}

index = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Test logiciel et test d'IA — démonstrations exécutées</title>
<meta name="description" content="Cycle de vie complet, chaîne de livraison avec anomalies et verdict GO, test d'un moteur de classement : tous les chiffres proviennent d'exécutions réelles.">
<link rel="stylesheet" href="static/site.css">
<style>
  .acc {{ max-width: 1000px; margin: 2rem auto 4rem; padding: 0 1.2rem; }}
  h1 {{ font-size: 1.7rem; line-height: 1.25; }}
  .sous {{ color: var(--text-dim); line-height: 1.7; }}
  .grille {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; margin: 1.6rem 0; }}
  .carte {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 1.1rem 1.2rem; }}
  .carte h2 {{ font-size: 1.02rem; margin: 0 0 .4rem; }}
  .carte p {{ color: var(--text-dim); font-size: .84rem; line-height: 1.6; margin: 0 0 .7rem; }}
  .carte a {{ font-weight: 700; }}
  .kpis {{ display: flex; gap: .7rem; flex-wrap: wrap; margin: 1.4rem 0; }}
  .kpi {{ flex: 1 1 140px; background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: .8rem .9rem; }}
  .kpi .n {{ font-size: 1.5rem; font-weight: 800; display: block; }}
  .kpi .l {{ font-size: .68rem; text-transform: uppercase; letter-spacing: .4px; color: #c9d1d9; font-weight: 600; }}
  ul.liste {{ line-height: 1.9; }}
  footer {{ margin-top: 2.5rem; padding-top: 1rem; border-top: 1px solid var(--border);
            color: var(--text-dim); font-size: .78rem; line-height: 1.7; }}
</style></head><body>
<div class="ciel"></div>
{ENTETE_INDEX}
<div class="page">
  <section class="heros">
    <div class="oeil">Démonstrations · tous les chiffres sortent d'exécutions réelles</div>
    <h1>Le test logiciel et le test d'IA, <span class="gradient">montrés plutôt que racontés</span></h1>
    <p class="chapo">
      Trois parcours construits sur les référentiels <strong>ISTQB CTFL v4.0.1</strong> (processus, techniques,
      anomalies), <strong>CT-AI v1.0.1</strong> (test des systèmes à base d'IA) et <strong>CT-GenAI v1.1</strong>
      (test avec l'IA générative). Chaque chiffre affiché provient d'une exécution : suites de tests jouées,
      scénarios navigateur dans un vrai Chromium, métriques mesurées sur un corpus étiqueté, couverture calculée.
    </p>
    <div class="etiquettes">
      <span class="etiquette vif">{LIFE['playwright']['nb_passes']}/{LIFE['playwright']['nb_scenarios']} scénarios navigateur</span>
      <span class="etiquette">Gherkin + Playwright</span>
      <span class="etiquette">pytest · coverage.py · Flask</span>
      <span class="etiquette">CTFL · CT-AI · CT-GenAI</span>
    </div>

    <div class="chiffres">
      <div class="chiffre"><span class="valeur cyan">{t['passes']}</span>
        <span class="legende">tests exécutés, 0 échec</span></div>
      <div class="chiffre"><span class="valeur violet">{m['precision']}</span>
        <span class="legende">précision · seuil {m['seuil']}</span></div>
      <div class="chiffre"><span class="valeur emeraude">{m['rappel']}</span>
        <span class="legende">rappel · métrique clé</span></div>
      <div class="chiffre"><span class="valeur ambre">{len(EVIDENCE['defauts'])}</span>
        <span class="legende">défauts corrigés, avant/après mesuré</span></div>
      <div class="chiffre"><span class="valeur cyan">{s['campagnes']['v3_regression']['campagne']['synthese']['reussis']}</span>
        <span class="legende">cas joués sur la chaîne de livraison</span></div>
    </div>
  </section>

  <div class="grille">
    <div class="carte">
      <div class="num-carte">PARCOURS 01</div>
      <h2>Cycle de vie complet de JobHunt</h2>
      <p>
        Une fonctionnalité réelle suivie de bout en bout : demande métier, user stories, stratégie de test,
        développement piloté par les tests (sorties console réelles), exécution des campagnes
        (unitaire, intégration, scénarios métier, navigateur), anomalies, corrections extraites de
        l'historique Git, non-régression mesurée, couverture calculée, intégration continue et
        amélioration continue. Chaque étape est rattachée aux référentiels CTFL, CT-AI et CT-GenAI.
      </p>
      <a class="lien" href="cycle-de-vie.html">Ouvrir le cycle de vie →</a>
    </div>
    <div class="carte">
      <div class="num-carte">PARCOURS 02</div>
      <h2>Chaîne de livraison virtuelle</h2>
      <p>
        Une demande métier, des user stories, une analyse de risque, douze cas de test conçus, une livraison
        défectueuse, des anomalies, un correctif… qui casse ailleurs — puis le second correctif et le verdict
        GO. Douze étapes jouables, campagnes réellement exécutées.
      </p>
      <a class="lien" href="chaine-de-livraison.html">Ouvrir la chaîne de livraison →</a>
    </div>
    <div class="carte">
      <div class="num-carte">PARCOURS 03</div>
      <h2>Vitrine du test d'IA</h2>
      <p>
        Le moteur de classement pris comme système à tester : matrice de confusion et seuils verrouillés,
        dix relations métamorphiques, entrées adverses, huit défauts trouvés puis corrigés avec l'avant/après
        mesuré, et les limites assumées du dispositif.
      </p>
      <a class="lien" href="vitrine-ct-ai.html">Ouvrir la vitrine →</a>
    </div>
  </div>

  <section class="sec">
    <div class="sec-tete"><div class="sec-num">06</div><h2>Dossier de portes — la démarche écrite</h2></div>
    <p class="sous">Les six portes de qualité du processus, rédigées avant l'exécution : cadrage du risque,
      qualité des données, métriques et seuils verrouillés, plan de test, techniques appliquées, journal
      d'usage de l'IA.</p>
    <div class="panneau">
      <ul class="propre">
        {''.join(f'<li><a href="{f}">{t}</a></li>' for f, t in index_docs)}
      </ul>
    </div>
  </section>

  <div class="note">
    Pages figées le {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} · Python {EVIDENCE['stack']['python']} ·
    pytest {EVIDENCE['stack']['pytest']} · Flask {EVIDENCE['stack']['flask']}. Les pages statiques ne
    ré-exécutent pas les campagnes : les exemples du banc d'essai sont précalculés par le même moteur, et
    chaque résultat affiché est un résultat d'exécution réel.
  </div>
</div>
{PIED}
<script src="static/site.js" defer></script>
</body></html>"""

with open(os.path.join(SORTIE, "index.html"), "w", encoding="utf-8") as fh:
    fh.write(index)

open(os.path.join(SORTIE, ".nojekyll"), "w").write("")

# ---------------------------------------------------------------------------
# 6. Contrôle de non-fuite : aucune coordonnée personnelle dans la publication
# ---------------------------------------------------------------------------
import re as _re

MOTIFS = [_re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
          _re.compile(r"(?:\+33|0)\s?[1-9](?:[\s.\-]?\d{2}){4}")]
FACTICES = ("example.com", "test.com", "example.org", "example.net")
suspects = []
for dossier, _, fichiers in os.walk(SORTIE):
    for nom in fichiers:
        if not nom.endswith((".html", ".css", ".js", ".md")):
            continue
        contenu = open(os.path.join(dossier, nom), encoding="utf-8", errors="ignore").read()
        for mail in MOTIFS[0].findall(contenu):
            if not any(mail.lower().endswith(d) for d in FACTICES):
                suspects.append(f"{nom} : {mail}")
        for tel in MOTIFS[1].findall(contenu):
            suspects.append(f"{nom} : {tel}")
if suspects:
    print("ARRÊT : coordonnées détectées dans la publication :")
    for suspect in suspects[:10]:
        print("  ", suspect)
    raise SystemExit(1)

fichiers_html = [f for f in sorted(os.listdir(SORTIE)) if f.endswith(".html")]
print(f"site statique écrit dans {SORTIE}")
for nom in fichiers_html:
    taille = os.path.getsize(os.path.join(SORTIE, nom))
    print(f"  {nom:34} {taille/1024:6.1f} Ko")
print(f"contrôle de non-fuite : OK ({len(fichiers_html)} pages)")
