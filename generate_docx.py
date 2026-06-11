from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

doc = Document()

section = doc.sections[0]
section.page_width = Cm(21)
section.page_height = Cm(29.7)
section.top_margin = Cm(1.5)
section.bottom_margin = Cm(1.2)
section.left_margin = Cm(1.8)
section.right_margin = Cm(1.8)

style = doc.styles['Normal']
font = style.font
font.name = 'Calibri'
font.size = Pt(10)

def add_title(text, size=22, color=RGBColor(0x11, 0x11, 0x11), bold=False):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.font.color.rgb = color
    r.bold = bold
    return p

def add_mixed_line(parts):
    """parts = [(text, size, color, bold), ...]"""
    p = doc.add_paragraph()
    for text, size, color, bold in parts:
        r = p.add_run(text)
        r.font.size = Pt(size)
        r.font.color.rgb = color
        r.bold = bold
    return p

def section_heading(text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(12)
    r.font.color.rgb = RGBColor(0x1A, 0x27, 0x44)
    r.bold = True
    r.underline = True
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(4)

# ═══ HEADER ═══
add_title('Thasin Jahangir', 22)
add_mixed_line([
    ('Consultant QA Senior · Freelance SASU', 13, RGBColor(0x1A, 0x4A, 0x9E), True)
])
add_mixed_line([
    ('Paris & Remote', 9, RGBColor(0x66,0x66,0x66), False),
    (' · ', 9, RGBColor(0x66,0x66,0x66), False),
    ('07 69 78 72 13', 9, RGBColor(0x66,0x66,0x66), False),
    (' · ', 9, RGBColor(0x66,0x66,0x66), False),
    ('thasin@live.com', 9, RGBColor(0x66,0x66,0x66), False),
    (' · ', 9, RGBColor(0x66,0x66,0x66), False),
    ('linkedin.com/in/thasin-j-47582635', 9, RGBColor(0x66,0x66,0x66), False),
])

# ═══ PROFIL ═══
section_heading('Profil')
p = doc.add_paragraph(
    "Senior QA — 12+ ans d'expérience sur projets complexes (web, mobile, ERP, bancaire) "
    "digitale, conformité réglementaire et applications cloud/mobile. Expert en pilotage "
    "des recettes fonctionnelles, gestion des cycles de non-régression et structuration "
    "des processus qualité. Expérience en banque, hospitality, SaaS, santé et cybersécurité. "
    "Habitué aux environnements complexes Mainframe, SAP, cloud et mobile."
)

# ═══ COMPÉTENCES ═══
section_heading('Compétences')
skills = [
    ("Pilotage QA & Gouvernance",
     "Stratégie de test, Plans de recette, Coordination QA, UAT, Non-régression, "
     "Reporting qualité, Go/No-Go, Gestion des anomalies, Suivi d'avancement, "
     "Couverture de tests, Tableaux de bord Jira, Indicateurs qualité, "
     "Relation client & parties prenantes, Agile / Scrum"),
    ("Recette fonctionnelle",
     "Tests web & mobile, Rédaction de cas de test depuis les user stories, "
     "Exécution de campagnes de validation, Validation de parcours critiques, "
     "Recette fonctionnelle, Gherkin, Appium (bases légères), Ranorex"),
    ("Outils & Environnements",
     "Jira, Xray, Zephyr, TestRail, Confluence, ServiceNow, SQL Oracle, "
     "Mainframe, Charles Proxy, Crashlytics, Dynatrace, Redmine, "
     "SAP BPC, SAP HANA, Windows / macOS / Linux, Android / iOS, VMware"),
    ("IA & Outils techniques",
     "Agents IA, Agentique, Prompt engineering, MCP, Claude Code, Python, Flask, "
     "GitHub Actions, LLMs cloud et locaux, Ollama, LM Studio, VS Code, Xcode"),
    ("Savoir-être",
     "Rigueur · Sens du détail · Esprit analytique · Autonomie · Proactivité · "
     "Communication claire · Collaboration · Priorisation · Curiosité technique · Orientation qualité")
]
for title, items in skills:
    p = doc.add_paragraph()
    r = p.add_run(title + '  ')
    r.bold = True
    r.font.size = Pt(9.5)
    r2 = p.add_run(items)
    r2.font.size = Pt(9)
    p.paragraph_format.space_after = Pt(1)

# ═══ EXPÉRIENCES ═══
section_heading('Expériences')
experiences = [
    ("BRED Banque Populaire — Facturation électronique", "Avr. 2023 — Auj.",
     "Consultant QA Senior — Freelance SASU", [
        "Piloter la recette fonctionnelle sur un programme de conformité réglementaire — dématérialisation des factures, périmètres P2P/O2C.",
        "Concevoir, planifier et exécuter des campagnes de tests fonctionnels, de régression ; rédiger et maintenir les plans de test, cahiers de recette, cas de tests, scénarios de test ; prioriser selon les risques fonctionnels et l'impact métier (applicable sur chaque mission).",
        "Coordonner des campagnes multi-équipes dans Jira/Xray — suivi de couverture, anomalies, Go/No-Go, synchro quotidienne équipes métier/BA/dev.",
        "Sécuriser les cycles de non-régression dans un environnement Mainframe / SQL Oracle.",
     ], "Jira, Xray, SQL Oracle, Mainframe, Corcentric, ServiceNow"),
    ("Accor — Applications mobiles internationales", "Sept. 2019 — Déc. 2022",
     "Référent QA Mobile — Consultant", [
        "Référent QA sur applications Android/iOS déployées dans 100+ pays : validation fonctionnelle, UAT et non-régression.",
        "Concevoir, planifier et exécuter des campagnes de tests fonctionnels, de régression et de compatibilité multi-versions sur une flotte terminaux Android/iOS physiques.",
        "Co-construire les user stories et scénarios Gherkin avec PO et développeurs pour aligner tests et automatisation mobile.",
        "Valider les flux transactionnels multi-appareils/multi-langues, reporting à la direction produit.",
     ], "Jira, Xray, Gherkin, Charles Proxy, Crashlytics, Android, iOS, Confluence"),
    ("Oodrive — Cloud souverain B2B", "Janv. 2017 — Avr. 2019",
     "Ingénieur Qualité Logiciel / Responsable QA", [
        "Responsable qualité sur applications critiques B2B/B2C cloud et desktop : WebSynchro (synchronisation fichiers), PostFiles (partage sécurisé), BoardNox (réunions gouvernance).",
        "Concevoir, planifier et exécuter des campagnes de tests fonctionnels, de régression, compatibilité multi-navigateurs et responsive design ; rédiger et maintenir les plans de test, cahiers de recette, cas de tests ; prioriser selon les risques.",
        "Structurer les pratiques QA : templates, critères, gestion anomalies dans Jira/Zephyr.",
        "Support N3 grands comptes, introduction Ranorex, et collaboration équipes dev/support/PO.",
     ], "Jira, Zephyr, Ranorex, Windows / macOS / Linux, SQL, VMware"),
    ("Visiodent — Logiciel santé", "Janv. 2016 — Sept. 2017",
     "Responsable Test / Consultant QA", [
        "Responsable QA sur le logiciel santé Veasy : validation fonctionnelle, non-régression.",
        "Concevoir, planifier et exécuter des campagnes de tests fonctionnels, de régression ; rédiger et maintenir les plans de test, cahiers de recette, cas de tests ; prioriser selon les risques.",
        "Intégrer la lecture Carte Vitale dans les scénarios de test.",
     ], "Jira, SQL, Windows, TestRail, VMware"),
    ("Vinci Construction — SAP BPC", "Juil. 2014 — Déc. 2015",
     "Consultant QA — intégration SAP BPC", [
        "Recette fonctionnelle d'applications SAP BPC : conformité, intégrité des données.",
        "Concevoir, planifier et exécuter des campagnes de tests fonctionnels, de régression ; rédiger et maintenir les plans de test, cahiers de recette, cas de tests ; prioriser selon les risques.",
        "Coordonner les campagnes multi-sites avec MOA, MOE, éditeur et hébergeur.",
     ], "SAP BPC, SAP HANA, Jira, SQL Oracle"),
    ("Profil Technology — Cybersécurité", "Oct. 2012 — Juin 2014",
     "Consultant QA — Référent WebFilter", [
        "Référent QA sur solutions filtrage web (WebFilter, Witigo, Bitdefender).",
        "Concevoir, planifier et exécuter des campagnes de tests fonctionnels, de régression et compatibilité multi-navigateurs ; rédiger et maintenir les plans de test, cahiers de recette, cas de tests ; prioriser selon les risques.",
        "Support N3 clients entreprises, collaboration équipes R&D et sécurité.",
     ], "Redmine, Windows / macOS / Linux, VMware, SQL, Bitdefender"),
    ("Année sabbatique", "2023",
     "Montée en compétences & projets personnels", [
        "Exploré 7 pays (Honduras, Colombie, Mexique, Guatemala, Nicaragua, Costa Rica, Panama).",
        "Création d'assistant IA agentique et pipelines QA automatisés (Python, LLMs, GitHub Actions).",
        "Développement d'une plateforme d'agrégation de news IA temps réel (Next.js, Supabase, OpenAI, 86 flux RSS).",
     ], "Python, Next.js, Supabase, LLMs, GitHub Actions, OpenAI")
]

for title, date, role, bullets, env in experiences:
    add_mixed_line([
        (title, 10.5, RGBColor(0x11,0x11,0x11), True),
        (f"    {date}", 9, RGBColor(0x88,0x88,0x88), False),
    ])
    add_mixed_line([
        (role, 9.5, RGBColor(0x1A,0x4A,0x9E), True),
    ])
    for b in bullets:
        bp = doc.add_paragraph(b, style='List Bullet')
        bp.paragraph_format.space_after = Pt(0)
        bp.paragraph_format.space_before = Pt(0)
        for run in bp.runs:
            run.font.size = Pt(9)
    ep = doc.add_paragraph(f"Environnement : {env}")
    for run in ep.runs:
        run.font.size = Pt(8.5)
        run.font.color.rgb = RGBColor(0x88,0x88,0x88)
    ep.paragraph_format.space_after = Pt(4)

# ═══ FORMATIONS ═══
section_heading('Formations')
formations = [
    ("Master Management de Projet — Génie Logiciel", "Université Paris Nanterre", "2009-2011"),
    ("Licence Informatique", "Université Paris Nanterre", "2006-2009"),
]
for title, school, years in formations:
    add_mixed_line([
        (title, 9.5, RGBColor(0x11,0x11,0x11), True),
        (f" — {school}", 9, RGBColor(0x66,0x66,0x66), False),
        (f" ({years})", 9, RGBColor(0x88,0x88,0x88), False),
    ])

# ═══ LANGUES ═══
section_heading('Langues')
langs = [
    ("Français", "natif"),
    ("Anglais", "courant (C1/C2)"),
    ("Espagnol", "professionnel"),
    ("Bengali", "courant"),
]
p = doc.add_paragraph()
for i, (lang, level) in enumerate(langs):
    if i > 0:
        p.add_run('  •  ').font.size = Pt(9)
    r = p.add_run(lang)
    r.font.size = Pt(9.5)
    r.bold = (lang == "Anglais")
    r2 = p.add_run(f' — {level}')
    r2.font.size = Pt(9)
    r2.font.color.rgb = RGBColor(0x88, 0x88, 0x88)

# Save
outpath = '/Users/jahangir/jobhunt/cv_tasin_jahangir.docx'
doc.save(outpath)
print(f'✅ Word ready: {outpath}')
