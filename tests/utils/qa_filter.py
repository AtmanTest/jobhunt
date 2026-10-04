"""Classification « QA logiciel » utilisée par les scénarios de filtrage.

Le produit ne dispose pas d'une fonction dédiée exposant cette règle ; elle est
décrite par les scénarios (``filtering/qa_filter.feature``,
``regression/bug_fixes.feature``) et déjà encodée dans les steps historiques de
scraping. On la centralise ici pour que les scénarios Given/When/Then la
partagent : un poste est retenu s'il porte un intitulé QA/test logiciel, et il
est écarté s'il vise le test de jeux vidéo, le management non technique, la
direction, ou un contexte pharma/clinical (cf. ``linkedin_scraper.EXCLUDE_TITLES``).
"""

TITLE_KEYWORDS = [
    "qa", "sdet", "quality assurance", "quality engineer",
    "test engineer", "test automation", "tester", "testing",
    "automation engineer", "test lead", "test manager", "qa lead",
    "qa engineer", "software test", "software testing", "test developer",
    "engineer in test", "test analyst", "analyste test",
    "testeur", "testeuse", "ingenieur test", "ingénieur test",
    "ivvq", "assurance qualite", "assurance qualité", "quality analyst",
]

# Rôles qui matchent des mots-clés QA mais ne sont pas du QA logiciel.
EXCLUDE_TITLE_KEYWORDS = [
    "game tester", "game testing", "game dev",
    "non-technical", "non technical",
    "director", "vice president", "head of", "vp ",
]

# Contextes métier hors périmètre QA logiciel.
EXCLUDE_DESCRIPTION_KEYWORDS = [
    "gmp", "pharmaceutical", "clinical", "pharmacy",
    "medical quality", "healthcare quality", "nursing", "registered nurse",
]


def classify_software_qa(title, description=""):
    """Retourne 1 si l'offre est du QA logiciel, sinon 0."""
    title_l = (title or "").lower()
    desc_l = (description or "").lower()

    if any(k in title_l for k in EXCLUDE_TITLE_KEYWORDS):
        return 0
    if any(k in desc_l for k in EXCLUDE_DESCRIPTION_KEYWORDS):
        return 0
    return 1 if any(k in title_l for k in TITLE_KEYWORDS) else 0
