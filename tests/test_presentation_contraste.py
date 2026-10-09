"""Présentation, contraste, bilan sans gravité, thème avocat (polices locales).

Plan : ``docs/plan-presentation-contrast-avocat.md`` (tester seul, rouge autorisé).

Contrats figés PAR CE FICHIER (dev : ne jamais modifier ce fichier) :

- Accueil (thème neutre) : pile système sobre
  ``system-ui, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`` sans pile
  monospace (ni ``Courier New`` ni ``JetBrains Mono`` ni ``monospace``
  générique dans le bloc ``.theme-neutre``) ; grille de cartes métiers avec
  images ``/static/img/...`` existantes (cyber : ``01-salle-serveurs.png`` ou
  ``02-alerte-rancon.png`` ; avocat : ``06-plaidoirie.jpg``), badges
  « Jouable » (cyber + avocat) et « Bientôt » (médecin), cartes jouables avec
  bouton d'action, cartes « Bientôt » atténuées non cliquables (pas de lien
  jouer) ; plus de « Avocat et médecin arrivent bientôt. ».
- Texte de présentation : « Choisis un métier, vis une affaire, prends des
  décisions, puis découvre ce que tu as aimé faire et les études qui mènent
  à ce métier. » ; l'ancienne phrase « quels métiers te correspondent »
  disparaît (hors ``AGENTS.md``, interdit de modification).
- Bilan (cyber ET avocat, après parcours complet) : plus de
  « Gravité de l'incident », plus de « / 99 » côté gravité, plus de jauge
  ``<meter>`` / ``role=meter`` sur la gravité ; garde la fin, le profil
  (``data-testid=profil``), les 5 barres (``data-trait`` + libellés accentués
  + mot « score »), les choix cités (>= 2 vrais labels) et la fiche métier
  avec les études (``data-testid=fiche-metier`` + formations).
- CSS : chaque thème (``.theme-neutre``, ``.theme-cyber``, ``.theme-avocat``)
  définit TOUTES les variables ``--fond, --carte, --texte, --titre, --accent,
  --accent-texte, --bordure, --surligne, --surligne-texte, --barre,
  --barre-fond`` ; contraste WCAG >= 4,5 sur ``--texte/--carte``,
  ``--titre/--carte``, ``--surligne-texte/--surligne`` et
  ``--accent-texte/--accent`` ; aucune couleur cyber en dur dans
  ``.theme-avocat``.
- Avocat : ``GET /partie?affaire=avocat-defense-001`` et ``GET /bilan``
  répondent 200 ; ``@font-face`` locales ``/static/fonts/...``
  (Pinyon Script + Cormorant Garamond), aucune URL Google Fonts ni http
  externe ; piles de secours serif/cursive pour rester lisible sans elles
  (aucun fichier réel supprimé par ces tests).

Rupture volontaire portée par tester seul :
``tests/test_bilan_enrichi.py::test_bilan_jauge_gravite_lisible_sans_texte_brut``
exige désormais l'ABSENCE de la jauge (voir ce fichier).

Style : fixtures app/client Flask + helpers page_texte/assert_sans_traceback
comme tests/test_web.py. Phase rouge TDD normale : ces tests échouent tant
que dev n'a pas implémenté (ils décrivent le comportement attendu).
"""

import html
import json
import re
import unicodedata
from pathlib import Path

import pytest

try:
    from app.web import creer_app
except ImportError:  # pragma: no cover - phase rouge TDD
    creer_app = None  # type: ignore[assignment]

RACINE = Path(__file__).resolve().parents[1]
CSS_PATH = RACINE / "static" / "style.css"
FONTS_DIR = RACINE / "static" / "fonts"
IMG_DIR = RACINE / "static" / "img"

AFFAIRE_CYBER = "cyber-alerte-serveur-rh"
AFFAIRE_AVOCAT = "avocat-defense-001"

TRAITS = ("analyser", "convaincre", "enqueter", "aider", "proteger")
LIBELLES_ACCENTUES = ("Analyser", "Convaincre", "Enquêter", "Aider", "Protéger")

NOUVELLE_PHRASE = (
    "Choisis un métier, vis une affaire, prends des décisions, "
    "puis découvre ce que tu as aimé faire et les études qui mènent à ce métier."
)
ANCIENNE_EXPRESSION = "quels métiers te correspondent"
ANCIENNE_MENTION_BIENTOT = "Avocat et médecin arrivent bientôt."

VARIABLES_ATTENDUES = (
    "--fond",
    "--carte",
    "--texte",
    "--titre",
    "--accent",
    "--accent-texte",
    "--bordure",
    "--surligne",
    "--surligne-texte",
    "--barre",
    "--barre-fond",
)
COUPLES_CONTRASTE = (
    ("--texte", "--carte"),
    ("--titre", "--carte"),
    ("--surligne-texte", "--surligne"),
    ("--accent-texte", "--accent"),
)
COULEURS_CYBER_INTERDITES_AVOCAT = (
    "#0b0f14",
    "#00e676",
    "#4da3ff",
    "#ff5252",
    "#131c28",
    "#1a2536",
    "#d9e6f2",
)
SEUIL_CONTRASTE_WCAG = 4.5


def page_texte(reponse):
    """Texte HTML décodé (entités HTML résolues pour comparer au JSON)."""
    return html.unescape(reponse.get_data(as_text=True))


def assert_sans_traceback(reponse):
    texte = reponse.get_data(as_text=True)
    assert "traceback" not in texte.lower(), "page d'erreur brute (traceback visible)"


def normaliser(texte):
    """Minuscules sans accents (Enquêter → enqueter, Bientôt → bientot)."""
    décomposé = unicodedata.normalize("NFKD", texte.lower())
    return "".join(c for c in décomposé if not unicodedata.combining(c))


def lire_css():
    assert CSS_PATH.exists(), "static/style.css manquant (contrat présentation)"
    return CSS_PATH.read_text(encoding="utf-8")


def blocs_theme(css, theme):
    """Concatène les déclarations de tous les blocs ``.theme-<nom>`` du CSS."""
    motif = re.compile(
        r"\.theme-" + re.escape(theme) + r"[^{]*\{([^}]*)\}",
        re.DOTALL,
    )
    return "\n".join(match.group(1) for match in motif.finditer(css))


def variables_theme(css, theme):
    """Dict variable → valeur brute pour un thème (depuis ses blocs CSS)."""
    declarations = blocs_theme(css, theme)
    trouvees = {}
    for variable in VARIABLES_ATTENDUES:
        match = re.search(
            re.escape(variable) + r"\s*:\s*([^;]+);", declarations
        )
        if match is not None:
            trouvees[variable] = match.group(1).strip()
    return trouvees


# --- helpers de contraste WCAG -------------------------------------------------


def _canal_vers_lineaire(canal):
    """Convertit un canal sRGB 0-255 en composante linéaire (formule WCAG)."""
    valeur = canal / 255.0
    if valeur <= 0.03928:
        return valeur / 12.92
    return ((valeur + 0.055) / 1.055) ** 2.4


def luminance_relative(rouge, vert, bleu):
    """Luminance relative WCAG d'une couleur sRGB."""
    return (
        0.2126 * _canal_vers_lineaire(rouge)
        + 0.7152 * _canal_vers_lineaire(vert)
        + 0.0722 * _canal_vers_lineaire(bleu)
    )


def ratio_contraste(couleur_claire, couleur_sombre):
    """Ratio de contraste WCAG entre deux couleurs (r, v, b)."""
    lum_claire = luminance_relative(*couleur_claire)
    lum_sombre = luminance_relative(*couleur_sombre)
    plus_claire = max(lum_claire, lum_sombre)
    plus_sombre = min(lum_claire, lum_sombre)
    return (plus_claire + 0.05) / (plus_sombre + 0.05)


def parse_couleur(valeur):
    """Parse ``#rgb``, ``#rrggbb``, ``rgb(...)`` / ``rgba(...)`` vers (r, v, b)."""
    texte = valeur.strip().lower().split("!")[0].strip()
    if texte.startswith("#"):
        chiffres = texte[1:]
        if len(chiffres) == 3:
            chiffres = "".join(c * 2 for c in chiffres)
        assert len(chiffres) == 6, f"couleur hexadécimale inattendue : {valeur!r}"
        return tuple(int(chiffres[i : i + 2], 16) for i in (0, 2, 4))
    match = re.match(r"rgba?\(([^)]*)\)", texte)
    assert match is not None, f"couleur non prise en charge : {valeur!r}"
    composantes = [morceau.strip() for morceau in match.group(1).split(",")]
    assert len(composantes) >= 3, f"couleur rgb incomplète : {valeur!r}"

    def _composante(morceau):
        morceau = morceau.strip()
        if morceau.endswith("%"):
            return round(float(morceau[:-1]) * 255 / 100)
        return int(float(morceau))

    return (_composante(composantes[0]), _composante(composantes[1]), _composante(composantes[2]))


# --- helpers de parcours -------------------------------------------------------


def charger_affaire_json(affaire_id):
    chemin = RACINE / "data" / "affaires" / f"{affaire_id}.json"
    with chemin.open(encoding="utf-8") as fichier:
        return json.load(fichier)


def chercher_chemin_complet(affaire, minimum_coups=6):
    """Cherche en profondeur un chemin vers une fin (suite None)."""
    pile = [(affaire["debut"], [])]
    visites = set()
    while pile:
        etape_id, coups = pile.pop()
        if etape_id is None:
            if len(coups) >= minimum_coups:
                return coups
            continue
        if len(coups) > 20:
            continue
        etape = affaire["etapes"][etape_id]
        for choix in etape["choix"]:
            nouveau = coups + [(etape_id, choix["id"])]
            suite = choix.get("suite")
            if suite is None:
                if len(nouveau) >= minimum_coups:
                    return nouveau
            elif (suite, len(nouveau)) not in visites:
                visites.add((suite, len(nouveau)))
                pile.append((suite, nouveau))
    return None


def jouer_parcours_complet(client, affaire_id, minimum_coups=6):
    """Joue un parcours complet (>= minimum_coups) et renvoie (affaire, chemin, bilan)."""
    affaire = charger_affaire_json(affaire_id)
    chemin = chercher_chemin_complet(affaire, minimum_coups=minimum_coups)
    assert chemin is not None, f"aucun chemin complet vers une fin ({affaire_id})"
    assert len(chemin) >= minimum_coups
    demarrage = client.get(f"/partie?affaire={affaire_id}")
    assert demarrage.status_code == 200
    for etape_id, choix_id in chemin:
        reponse = client.post(
            "/jouer",
            data={"affaire": affaire_id, "etape": etape_id, "choix": choix_id},
            follow_redirects=True,
        )
        assert reponse.status_code == 200
        assert_sans_traceback(reponse)
    bilan = client.get("/bilan")
    assert bilan.status_code == 200
    assert_sans_traceback(bilan)
    return affaire, chemin, bilan


@pytest.fixture()
def app():
    assert creer_app is not None, (
        "factory app.web.creer_app manquante (phase rouge TDD, étape non implémentée)"
    )
    application = creer_app()
    application.config.update(TESTING=True, SECRET_KEY="secret-test-tdd")
    application.config["PROPAGATE_EXCEPTIONS"] = False
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


# --- 1. police de l'accueil (thème neutre) -------------------------------------


def test_accueil_theme_neutre_sans_pile_monospace():
    css = lire_css()
    bloc = blocs_theme(css, "neutre")

    assert bloc.strip() != "", ".theme-neutre absent de static/style.css"
    minuscules = bloc.lower()
    for interdite in ("courier new", "jetbrains mono", "monospace"):
        assert interdite not in minuscules, (
            f"l'accueil (thème neutre) ne doit pas utiliser de pile monospace ({interdite!r})"
        )


def test_accueil_theme_neutre_pile_systeme_sobre():
    css = lire_css()
    bloc = blocs_theme(css, "neutre").lower()

    for morceau in ("system-ui", "segoe ui", "roboto", "helvetica", "arial", "sans-serif"):
        assert morceau in bloc, (
            f"pile système sobre attendue sur l'accueil (.theme-neutre) : {morceau!r} manquant"
        )


# --- 2. cartes et badges de l'accueil ------------------------------------------


def test_accueil_grille_cartes_metiers_avec_images_existantes(client):
    reponse = client.get("/")

    assert reponse.status_code == 200
    brut = reponse.get_data(as_text=True)
    assert re.search(r'class="[^"]*(metiers|grille|grid|cartes|cards)[^"]*"', brut) is not None, (
        "grille de cartes métiers absente de l'accueil"
    )
    sources = re.findall(r'<img[^>]+src="([^"]+)"', brut)
    images_statiques = [src for src in sources if src.startswith("/static/img/")]
    assert len(images_statiques) >= 2, (
        f"attendues >= 2 images métiers vers /static/img/..., reçues {images_statiques!r}"
    )
    for source in images_statiques:
        relatif = source[len("/static/") :]
        assert (RACINE / "static" / relatif).is_file(), (
            f"image d'accueil inexistante dans static/ : {source!r}"
        )


def test_accueil_images_cyber_et_avocat_attendues(client):
    reponse = client.get("/")
    brut = reponse.get_data(as_text=True)

    assert "01-salle-serveurs.png" in brut or "02-alerte-rancon.png" in brut, (
        "carte cyber : image 01-salle-serveurs.png ou 02-alerte-rancon.png attendue"
    )
    assert "06-plaidoirie.jpg" in brut, "carte avocat : image 06-plaidoirie.jpg attendue"


def test_accueil_badges_jouable_et_bientot(client):
    reponse = client.get("/")
    normalisé = normaliser(page_texte(reponse))
    brut = reponse.get_data(as_text=True)

    assert normalisé.count("jouable") >= 2, "badges « Jouable » (cyber + avocat) attendus"
    assert "bientot" in normalisé, "badge « Bientôt » (médecin) attendu"
    assert "badge-jouable" in brut, "classe badge-jouable absente de l'accueil"
    assert "badge-bientot" in brut, "classe badge-bientot absente de l'accueil"


def test_accueil_cartes_jouables_avec_bouton_d_action(client):
    reponse = client.get("/")
    brut = reponse.get_data(as_text=True)
    blocs = re.findall(r"<li[^>]*>.*?</li>", brut, flags=re.DOTALL | re.IGNORECASE)

    for indice in (AFFAIRE_CYBER, AFFAIRE_AVOCAT):
        cartes = [bloc for bloc in blocs if indice in bloc]
        assert cartes, f"carte jouable introuvable pour {indice!r}"
        carte = cartes[0]
        assert re.search(r'class="[^"]*\bbouton\b[^"]*"', carte) is not None, (
            f"carte {indice!r} : bouton d'action (class bouton) attendu"
        )
        assert "partie?affaire=" in carte or "/jouer" in carte, (
            f"carte {indice!r} : le bouton doit mener vers la partie à jouer"
        )


def test_accueil_carte_bientot_attenuee_non_cliquable(client):
    reponse = client.get("/")
    brut = reponse.get_data(as_text=True)
    blocs = re.findall(r"<li[^>]*>.*?</li>", brut, flags=re.DOTALL | re.IGNORECASE)
    cartes_medecin = [bloc for bloc in blocs if "decin" in normaliser(bloc)]
    assert cartes_medecin, "carte médecin introuvable sur l'accueil"
    carte = cartes_medecin[0]

    assert "bientot" in normaliser(carte), "la carte médecin doit porter le badge « Bientôt »"
    assert "partie?affaire=" not in carte and "/jouer" not in carte, (
        "la carte « Bientôt » ne doit contenir aucun lien jouer"
    )
    ouverture = re.match(r"<li[^>]*>", carte, flags=re.IGNORECASE)
    assert ouverture is not None
    motif_classe_attenuee = r"bientot|attenu|desactiv|inactif|indisponible|non-cliquable"
    assert re.search(motif_classe_attenuee, ouverture.group(0).lower()) is not None, (
        "la carte « Bientôt » doit être atténuée (classe bientot/atténuée sur la carte)"
    )


def test_accueil_sans_ancienne_mention_arrivee_bientot(client):
    reponse = client.get("/")

    assert ANCIENNE_MENTION_BIENTOT not in page_texte(reponse), (
        f"mention à supprimer au profit des badges : {ANCIENNE_MENTION_BIENTOT!r}"
    )


# --- 3. nouvelle phrase de présentation ----------------------------------------


def test_accueil_nouvelle_phrase_de_presentation(client):
    reponse = client.get("/")

    assert reponse.status_code == 200
    assert NOUVELLE_PHRASE in page_texte(reponse), (
        "nouvelle phrase de présentation absente de l'accueil"
    )


def test_accueil_sans_ancienne_phrase_metiers_correspondent(client):
    reponse = client.get("/")
    normalisé = normaliser(page_texte(reponse))

    assert normaliser(ANCIENNE_EXPRESSION) not in normalisé, (
        "ancienne phrase à remplacer : « quels métiers te correspondent »"
    )


# --- 4. bilan sans gravité (cyber + avocat) ------------------------------------


@pytest.mark.parametrize("affaire_id", [AFFAIRE_CYBER, AFFAIRE_AVOCAT])
def test_bilan_sans_gravite_ni_jauge(client, affaire_id):
    _affaire, _chemin, bilan = jouer_parcours_complet(client, affaire_id)
    texte = page_texte(bilan)
    brut = bilan.get_data(as_text=True)
    bas = brut.lower()

    assert "Gravité de l'incident" not in texte, (
        "le bilan ne doit plus afficher « Gravité de l'incident » (calcul conservé côté moteur)"
    )
    assert "/ 99" not in texte, "le bilan ne doit plus afficher « / 99 » côté gravité"
    assert "<meter" not in bas, "la jauge <meter> de gravité doit être supprimée du bilan"
    assert 'role="meter"' not in bas and "role='meter'" not in bas, (
        "aucun role=meter de gravité ne doit rester dans le bilan"
    )


@pytest.mark.parametrize("affaire_id", [AFFAIRE_CYBER, AFFAIRE_AVOCAT])
def test_bilan_garde_fin_profil_barres_citations_et_fiche_metier(client, affaire_id):
    affaire, chemin, bilan = jouer_parcours_complet(client, affaire_id)
    texte = page_texte(bilan)
    brut = bilan.get_data(as_text=True)
    bas = brut.lower()

    titres_fins = [fin["titre"] for fin in affaire["fins"]]
    assert any(titre in texte for titre in titres_fins), "le bilan doit toujours afficher la fin"
    assert 'data-testid="profil"' in brut or "data-testid='profil'" in brut, (
        "le bilan doit garder le profil (data-testid=profil)"
    )
    for trait in TRAITS:
        assert f'data-trait="{trait}"' in bas or f"data-trait='{trait}'" in bas, (
            f"barre manquante pour le trait : {trait}"
        )
    for libellé in LIBELLES_ACCENTUES:
        assert libellé in texte, f"libellé accentué manquant : {libellé}"
    assert "score" in normaliser(texte), "le mot « score » doit rester présent"
    labels_choisis = [
        next(
            choix["label"]
            for choix in affaire["etapes"][etape_id]["choix"]
            if choix["id"] == choix_id
        )
        for etape_id, choix_id in chemin
    ]
    trouves = [label for label in labels_choisis if label in texte]
    assert len(trouves) >= 2, "le bilan cite moins de 2 vrais choix du joueur"
    assert 'data-testid="fiche-metier"' in brut or "data-testid='fiche-metier'" in brut, (
        "le bilan doit garder la fiche métier (data-testid=fiche-metier)"
    )
    with (RACINE / "data" / "metiers.json").open(encoding="utf-8") as fichier:
        metiers = json.load(fichier)
    code_metier = affaire.get("metier", affaire.get("theme"))
    formations = metiers[code_metier]["formations"]

    def _formation_affichee(formation):
        """Vrai si la formation est visible, quelle que soit la mise en forme HTML."""
        if isinstance(formation, str):
            return formation in texte
        valeurs_non_vides = [
            formation[cle]
            for cle in ("etape", "duree", "description")
            if formation.get(cle)
        ]
        return bool(valeurs_non_vides) and all(
            champ in texte for champ in valeurs_non_vides
        )

    assert any(_formation_affichee(formation) for formation in formations), (
        "la fiche métier doit afficher les études (formations)"
    )


# --- 5. variables CSS par thème -------------------------------------------------


@pytest.mark.parametrize("theme", ["neutre", "cyber", "avocat"])
def test_variables_css_completes_par_theme(theme):
    css = lire_css()
    declarations = blocs_theme(css, theme)

    assert declarations.strip() != "", f".theme-{theme} absent de static/style.css"
    manquantes = [
        variable
        for variable in VARIABLES_ATTENDUES
        if re.search(re.escape(variable) + r"\s*:", declarations) is None
    ]
    assert not manquantes, (
        f".theme-{theme} : variables manquantes : {', '.join(manquantes)}"
    )


# --- 6. contraste WCAG >= 4,5 ---------------------------------------------------


@pytest.mark.parametrize("theme", ["neutre", "cyber", "avocat"])
def test_contraste_wcag_suffisant_par_theme(theme):
    css = lire_css()
    valeurs = variables_theme(css, theme)

    for variable in VARIABLES_ATTENDUES:
        assert variable in valeurs, f".theme-{theme} : variable {variable} non définie"
    for premier, second in COUPLES_CONTRASTE:
        premier_rgb = parse_couleur(valeurs[premier])
        second_rgb = parse_couleur(valeurs[second])
        ratio = ratio_contraste(premier_rgb, second_rgb)
        assert ratio >= SEUIL_CONTRASTE_WCAG, (
            f".theme-{theme} : contraste {premier} sur {second} = {ratio:.2f} "
            f"(attendu >= {SEUIL_CONTRASTE_WCAG})"
        )


# --- 7. pas de fuite cyber dans le thème avocat ---------------------------------


def test_aucune_couleur_cyber_en_dur_dans_theme_avocat():
    css = lire_css()
    bloc_avocat = blocs_theme(css, "avocat").lower()

    assert bloc_avocat.strip() != "", ".theme-avocat absent de static/style.css"
    fuites = [
        couleur for couleur in COULEURS_CYBER_INTERDITES_AVOCAT if couleur in bloc_avocat
    ]
    assert not fuites, (
        f"couleurs cyber en dur dans .theme-avocat : {', '.join(fuites)} "
        "(passer par les variables du thème avocat)"
    )


# --- 8. pages avocat + polices locales ------------------------------------------


def test_partie_avocat_repond_200(client):
    reponse = client.get(f"/partie?affaire={AFFAIRE_AVOCAT}")

    assert reponse.status_code == 200
    assert_sans_traceback(reponse)
    assert reponse.get_data(as_text=True).strip() != ""


def test_bilan_avocat_apres_parcours_complet_repond_200(client):
    _affaire, _chemin, bilan = jouer_parcours_complet(client, AFFAIRE_AVOCAT)

    assert bilan.status_code == 200
    assert_sans_traceback(bilan)
    assert page_texte(bilan).strip() != ""


def test_css_font_face_polices_locales_sans_url_externe():
    css = lire_css()
    bas = css.lower()

    assert "@font-face" in bas, "@font-face manquant (polices locales exigées)"
    assert "/static/fonts/" in css, "chemins /static/fonts/... attendus dans le CSS"
    assert "pinyon" in bas, "police Pinyon Script non référencée dans le CSS"
    assert "cormorant" in bas or "garamond" in bas, (
        "police Cormorant Garamond non référencée dans le CSS"
    )
    for marqueur in ("googleapis", "gstatic", "fonts.googleapis", "google fonts"):
        assert marqueur not in bas, (
            f"aucune dépendance Google Fonts : {marqueur!r} trouvé dans le CSS"
        )
    assert "http://" not in bas and "https://" not in bas, (
        "aucune URL http externe dans le CSS (polices 100 % locales)"
    )


def test_polices_secours_serif_cursive_sans_supprimer_les_fichiers(client):
    css = lire_css()
    bas = css.lower()

    for morceau in ("palatino linotype", "book antiqua", "georgia", "serif"):
        assert morceau in bas, (
            f"pile de secours serif attendue (texte courant) : {morceau!r} manquant"
        )
    for morceau in ("segoe script", "lucida handwriting", "brush script mt", "cursive"):
        assert morceau in bas, (
            f"pile de secours cursive attendue (titres) : {morceau!r} manquant"
        )
    for fichier in (
        "PinyonScript-Regular.ttf",
        "CormorantGaramond-VariableFont_wght.ttf",
        "CormorantGaramond-Italic-VariableFont_wght.ttf",
    ):
        assert (FONTS_DIR / fichier).is_file(), (
            f"fichier de police manquant (ne jamais le supprimer) : {fichier}"
        )
    assert IMG_DIR.is_dir(), "static/img/ manquant"
    assert client.get(f"/partie?affaire={AFFAIRE_AVOCAT}").status_code == 200
