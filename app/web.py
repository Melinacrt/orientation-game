"""Application web Flask du jeu Orientation Game (sans IA).

Le jeu se joue dans le navigateur à partir des affaires JSON validées :
``GET /`` (accueil), ``GET /partie`` (contexte + étape), ``POST /jouer``
(un choix, état en session) et ``GET /bilan`` (fin + scores + citations).
Toute entrée utilisateur est validée et toute erreur renvoie une page
propre en français, jamais une traceback brute.
"""

from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path
from typing import Any

from flask import Flask, redirect, render_template, request, session, url_for

from app.affaires import charger_affaire
from app.moteur import TRAITS, calculer_bilan, jouer_coup, nouvelle_partie

RACINE = Path(__file__).resolve().parents[1]
DOSSIER_AFFAIRES = RACINE / "data" / "affaires"
FICHIER_PROFILS = RACINE / "data" / "profils.json"
FICHIER_METIERS = RACINE / "data" / "metiers.json"
LONGUEUR_MAX = 200
MOTIF_AFFAIRE = re.compile(r"^[a-z0-9-]+$")
MOTIF_THEME = re.compile(r"^[a-z0-9-]+$")
CLE_SECRETE_DEV = "cle-dev-locale-non-secrete-a-changer"
MESSAGE_RETOUR_ARRIERE = "Tu étais revenu en arrière : voici l'étape en cours."
LIBELLES_TRAITS = {
    "analyser": "Analyser",
    "convaincre": "Convaincre",
    "enqueter": "Enquêter",
    "aider": "Aider",
    "proteger": "Protéger",
}


def creer_app() -> Flask:
    """Crée et configure l'application Flask du jeu.

    Returns:
        L'application Flask prête à servir (templates + statiques inclus).
    """
    application = Flask(
        __name__,
        template_folder=str(RACINE / "templates"),
        static_folder=str(RACINE / "static"),
    )
    application.secret_key = os.environ.get("SECRET_KEY", CLE_SECRETE_DEV)

    @application.get("/")
    def accueil() -> str:
        return render_template("accueil.html", theme="neutre")

    @application.get("/partie")
    def partie() -> Any:
        if "affaire" not in request.args:
            return _reponse_etape_ou_accueil()
        try:
            affaire_id = _valider_id_affaire(request.args.get("affaire"))
        except ValueError as exc:
            return _page_erreur(400, str(exc))
        try:
            affaire = _charger_affaire(affaire_id)
        except ValueError as exc:
            return _page_erreur(404, str(exc))
        etat = nouvelle_partie(affaire)
        session["affaire_id"] = affaire_id
        session["etat"] = etat
        # Nouvelle partie : le message de retour arrière ne doit pas fuiter
        # d'une ancienne partie et le chronomètre repart de zéro (jamais
        # écrasé ensuite : jouer / afficher_jouer / bilan le conservent).
        session.pop("message_retour", None)
        import time

        session["debut_ts"] = time.time()
        return _page_partie(affaire, affaire_id, etat, consequence=None), 200

    @application.get("/jouer")
    def afficher_jouer() -> Any:
        return _reponse_etape_ou_accueil()

    @application.post("/jouer")
    def jouer() -> Any:
        try:
            affaire_id = _valider_id_affaire(request.form.get("affaire"))
            etape_id = _exiger_champ(request.form.get("etape"), "etape")
            choix_id = _exiger_champ(request.form.get("choix"), "choix")
            affaire = _charger_affaire(affaire_id)
        except ValueError as exc:
            return _page_erreur(400, str(exc))
        try:
            etat = _etat_session(affaire, affaire_id)
            courante = etat.get("etape_courante")
            if courante is None:
                return redirect(url_for("bilan"), code=303)
            if etape_id != courante:
                etapes = affaire.get("etapes", {})
                if isinstance(etapes, dict) and etape_id in etapes:
                    # Retour arrière : étape connue de l'affaire mais qui
                    # n'est plus l'étape courante (bouton précédent du
                    # navigateur). La partie reste intacte : on mémorise un
                    # message affiché une seule fois sur l'étape en cours.
                    session["message_retour"] = MESSAGE_RETOUR_ARRIERE
                    return redirect(url_for("afficher_jouer"), code=303)
                raise ValueError(
                    "Cette étape ne correspond pas à la partie en cours : "
                    "choix invalide. Retour à l'accueil pour recommencer."
                )
            etat = jouer_coup(affaire, etat, etape_id, choix_id)
        except ValueError as exc:
            return _page_erreur(400, str(exc))
        session["affaire_id"] = affaire_id
        session["etat"] = etat
        if etat.get("etape_courante") is None:
            return redirect(url_for("bilan"), code=303)
        return redirect(url_for("afficher_jouer"), code=303)

    @application.get("/bilan")
    def bilan() -> Any:
        etat_brut = session.get("etat")
        affaire_stockee = session.get("affaire_id")
        if not isinstance(etat_brut, dict) or not isinstance(affaire_stockee, str):
            return redirect(url_for("accueil"))
        try:
            affaire_id = _valider_id_affaire(affaire_stockee)
            affaire = _charger_affaire(affaire_id)
            etat = copy.deepcopy(etat_brut)
            resultat = calculer_bilan(affaire, etat, FICHIER_PROFILS)
        except ValueError as exc:
            return _page_erreur(400, str(exc))
        return _page_bilan(affaire, affaire_id, etat, resultat), 200

    @application.errorhandler(400)
    def erreur_400(exc: Any) -> tuple[str, int]:
        message = _message_erreur(exc, "Demande invalide ou incorrecte.")
        return _page_erreur(400, f"{message} Retour à l'accueil.")

    @application.errorhandler(404)
    def erreur_404(exc: Any) -> tuple[str, int]:
        _ = exc
        return _page_erreur(
            404,
            "Page introuvable : cette page n'existe pas. "
            "Retour à l'accueil pour recommencer.",
        )

    @application.errorhandler(405)
    def erreur_405(exc: Any) -> tuple[str, int]:
        _ = exc
        return _page_erreur(
            405,
            "Méthode non autorisée : cette méthode n'est pas autorisée ici. "
            "Retour à l'accueil pour recommencer.",
        )

    @application.errorhandler(500)
    def erreur_500(exc: Any) -> tuple[str, int]:
        _ = exc
        return _page_erreur(
            500,
            "Oups, une erreur interne est survenue. Désolée, "
            "un problème technique nous empêche d'afficher cette page. "
            "Retour à l'accueil pour recommencer.",
        )

    return application


def _consequence_derniere(etat: dict) -> str | None:
    historique = etat.get("historique")
    if isinstance(historique, list) and historique:
        derniere = historique[-1]
        if isinstance(derniere, dict):
            valeur = derniere.get("consequence", "")
            if isinstance(valeur, str) and valeur:
                return valeur
    return None


def _theme_affaire(affaire: dict) -> str:
    """Nom du thème d'habillage d'une affaire (repli « cyber »).

    Les anciennes sessions ou affaires sans ``theme`` restent habillées
    avec le thème cyber ; un thème invalide ne fait jamais échouer la page.
    """
    theme = affaire.get("theme", "cyber")
    if isinstance(theme, str) and MOTIF_THEME.match(theme):
        return theme
    return "cyber"


def _message_retour_une_fois() -> str | None:
    """Lit puis efface le message de retour arrière (affiché une fois)."""
    message = session.pop("message_retour", None)
    if isinstance(message, str) and message.strip():
        return message
    return None


def _reponse_etape_ou_accueil() -> Any:
    etat_brut = session.get("etat")
    affaire_stockee = session.get("affaire_id")
    if not isinstance(etat_brut, dict) or not isinstance(affaire_stockee, str):
        return redirect(url_for("accueil"))
    try:
        affaire_id = _valider_id_affaire(affaire_stockee)
        affaire = _charger_affaire(affaire_id)
    except ValueError:
        return redirect(url_for("accueil"))
    etat = copy.deepcopy(etat_brut)
    if etat.get("etape_courante") is None:
        return redirect(url_for("bilan"))
    courante = etat.get("etape_courante")
    etapes = affaire.get("etapes", {})
    if not isinstance(courante, str) or courante not in etapes:
        return redirect(url_for("accueil"))
    message = _message_retour_une_fois()
    return (
        _page_partie(
            affaire, affaire_id, etat, _consequence_derniere(etat), message
        ),
        200,
    )


def _page_partie(
    affaire: dict,
    affaire_id: str,
    etat: dict,
    consequence: str | None,
    message_retour: str | None = None,
) -> str:
    from app.moteur import tableau_de_bord

    etape_id = str(etat.get("etape_courante"))
    etape = affaire["etapes"][etape_id]
    historique = etat.get("historique")
    numero = len(historique) + 1 if isinstance(historique, list) else 1
    tableau = tableau_de_bord(affaire, etat)
    image_url = _image_url_etape(etape)
    if isinstance(etape, dict) and image_url is not None:
        image_alt = etape.get("image_alt")
    else:
        image_alt = None
    debut = _debut_ts()
    return render_template(
        "partie.html",
        affaire=affaire,
        affaire_id=affaire_id,
        etape_id=etape_id,
        etape=etape,
        consequence=consequence,
        message_retour=message_retour,
        numero=numero,
        total=len(affaire["etapes"]),
        tableau=tableau,
        image_url=image_url,
        image_alt=image_alt,
        chrono=_texte_chrono(debut),
        debut_ts=int(debut),
        theme=_theme_affaire(affaire),
    )


def _debut_ts() -> float:
    """Heure de début de la partie (session, posée une fois, jamais écrasée)."""
    import time

    valeur = session.get("debut_ts")
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        valeur = time.time()
        session["debut_ts"] = valeur
    return float(valeur)


def _texte_chrono(debut: float) -> str:
    """Temps écoulé depuis ``debut`` au format MM:SS (chrono temps réel)."""
    import time

    ecoule = max(0, int(time.time() - debut))
    return f"{ecoule // 60:02d}:{ecoule % 60:02d}"


def _image_url_etape(etape: object) -> str | None:
    """URL sûre ``/static/img/...`` d'une étape, ou None.

    Ne renvoie une URL que si l'étape déclare une ``image`` valide (chaîne
    relative sous ``img/``, minuscules/chiffres/tirets, extension autorisée,
    200 caractères maximum, sans ``..`` ni URL) avec un ``image_alt`` non
    vide, et si le fichier existe vraiment dans ``static/img/``. Sinon None :
    la page reste en 200 sans <img> cassé ni traceback.
    """
    motif = re.compile(r"^img/[a-z0-9\-_/]+\.(png|jpg|jpeg|webp|svg)$")
    if not isinstance(etape, dict):
        return None
    image = etape.get("image")
    if image is None:
        return None
    alt = etape.get("image_alt")
    if (
        not isinstance(image, str)
        or not image.strip()
        or len(image) > LONGUEUR_MAX
        or ".." in image
        or "\\" in image
        or image.startswith(("/", "http"))
        or not motif.match(image)
    ):
        return None
    if not isinstance(alt, str) or not alt.strip():
        return None
    dossier = RACINE / "static" / "img"
    candidat = dossier / image[len("img/") :]
    try:
        cible = candidat.resolve()
        base = dossier.resolve()
    except OSError:
        return None
    if base not in cible.parents:
        return None
    if not cible.is_file():
        return None
    return url_for("static", filename=image)


def _charger_metiers() -> dict:
    """Charge ``data/metiers.json`` (dict par code métier, repli ``{}``).

    Toute anomalie (fichier absent ou illisible) donne un dictionnaire vide :
    le bilan affiche alors un repli propre, jamais de traceback ni de 500.
    """
    try:
        contenu = FICHIER_METIERS.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        donnees = json.loads(contenu)
    except ValueError:
        return {}
    return donnees if isinstance(donnees, dict) else {}


def _fiche_et_autres_metiers(affaire: dict) -> tuple[dict | None, list]:
    """Fiche du métier joué + liste des autres métiers (repli propre).

    La fiche est résolue via ``affaire["metier"]`` puis ``affaire["theme"]``.
    Chaque entrée retournée est un dict ``{"code", "titre", "jouable"}`` ;
    les entrées malformées sont ignorées sans lever d'erreur.
    """
    metiers = _charger_metiers()
    if not metiers:
        return None, []
    code: str | None = None
    for cle in (affaire.get("metier"), affaire.get("theme")):
        if isinstance(cle, str) and cle in metiers:
            code = cle
            break
    fiche: dict | None = None
    if code is not None:
        candidate = metiers.get(code)
        fiche = candidate if isinstance(candidate, dict) else None
    autres = []
    for codemetier, entree in metiers.items():
        if not isinstance(entree, dict):
            continue
        titre = entree.get("titre")
        if not isinstance(titre, str) or not titre.strip():
            continue
        jouable = entree.get("jouable")
        autres.append(
            {
                "code": codemetier,
                "titre": titre,
                "jouable": jouable if isinstance(jouable, bool) else False,
            }
        )
    return fiche, autres


def _page_bilan(affaire: dict, affaire_id: str, etat: dict, bilan: dict) -> str:
    _ = etat
    fiche_metier, autres_metiers = _fiche_et_autres_metiers(affaire)
    return render_template(
        "bilan.html",
        affaire=affaire,
        affaire_id=affaire_id,
        bilan=bilan,
        traits=list(TRAITS),
        libelles=dict(LIBELLES_TRAITS),
        score_max=_score_max_bilan(bilan),
        traits_dominants=_dominants_bilan(bilan),
        niveau_gravite=_niveau_gravite_bilan(bilan),
        gravite_max=_gravite_max_bilan(bilan),
        theme=_theme_affaire(affaire),
        fiche_metier=fiche_metier,
        autres_metiers=autres_metiers,
    )


def _scores_bilan(bilan: dict) -> dict:
    scores = bilan.get("scores")
    return dict(scores) if isinstance(scores, dict) else {}


def _score_max_bilan(bilan: dict) -> int:
    maximum = 0
    for trait in TRAITS:
        valeur = _scores_bilan(bilan).get(trait, 0)
        if isinstance(valeur, int) and not isinstance(valeur, bool):
            if valeur > maximum:
                maximum = valeur
    return maximum


def _dominants_bilan(bilan: dict) -> list:
    dominants = bilan.get("traits_dominants")
    if isinstance(dominants, list):
        choisis = [trait for trait in dominants if trait in TRAITS]
    else:
        choisis = []
    if len(choisis) >= 2:
        return choisis[:2]
    scores = _scores_bilan(bilan)
    ordre = sorted(
        TRAITS, key=lambda nom: (-_score_nombre(scores, nom), TRAITS.index(nom))
    )
    for trait in ordre:
        if trait not in choisis:
            choisis.append(trait)
        if len(choisis) == 2:
            break
    return choisis


def _score_nombre(scores: dict, trait: str) -> int:
    valeur = scores.get(trait, 0)
    if isinstance(valeur, int) and not isinstance(valeur, bool) and valeur > 0:
        return valeur
    return 0


def _niveau_gravite_bilan(bilan: dict) -> str:
    niveau = bilan.get("niveau_gravite")
    if isinstance(niveau, str) and niveau.strip():
        return niveau
    gravite = bilan.get("gravite", 0)
    if not isinstance(gravite, int) or isinstance(gravite, bool):
        gravite = 0
    if gravite <= 2:
        return "Impact maîtrisé"
    if gravite <= 6:
        return "Impact limité"
    return "Impact élevé"


def _gravite_max_bilan(bilan: dict) -> int:
    maximum = bilan.get("gravite_max")
    if isinstance(maximum, int) and not isinstance(maximum, bool) and maximum > 0:
        return maximum
    return 99


def _page_erreur(code: int, message: str) -> tuple[str, int]:
    return (
        render_template("erreur.html", code=code, message=message, theme="neutre"),
        code,
    )


def _message_erreur(exc: Any, defaut: str) -> str:
    description = getattr(exc, "description", None)
    if isinstance(description, str) and description.strip():
        return description
    return defaut


def _exiger_champ(valeur: object, nom: str) -> str:
    if not isinstance(valeur, str):
        raise ValueError(
            f"Le champ « {nom} » doit être une chaîne de caractères : "
            "choix invalide. Retour à l'accueil pour recommencer."
        )
    if not valeur.strip():
        raise ValueError(
            f"Le champ « {nom} » est manquant ou vide : choix invalide. "
            "Retour à l'accueil pour recommencer."
        )
    if len(valeur) > LONGUEUR_MAX:
        raise ValueError(
            f"Le champ « {nom} » ne doit pas dépasser {LONGUEUR_MAX} caractères : "
            "choix invalide. Retour à l'accueil pour recommencer."
        )
    return valeur


def _valider_id_affaire(valeur: object) -> str:
    identifiant = _exiger_champ(valeur, "affaire")
    if not MOTIF_AFFAIRE.match(identifiant):
        raise ValueError(
            "L'identifiant d'affaire est invalide : caractères incorrects "
            "(lettres minuscules, chiffres et tirets uniquement). "
            "Retour à l'accueil pour recommencer."
        )
    return identifiant


def _charger_affaire(affaire_id: str) -> dict:
    chemin = DOSSIER_AFFAIRES / f"{affaire_id}.json"
    try:
        return charger_affaire(chemin)
    except ValueError as exc:
        texte = str(exc)
        if "introuvable" in texte:
            raise ValueError(
                f"L'affaire « {affaire_id} » est introuvable : affaire inconnue. "
                "Retour à l'accueil pour choisir une affaire."
            ) from exc
        raise ValueError(
            f"L'affaire « {affaire_id} » est invalide et impossible à charger. "
            "Retour à l'accueil pour recommencer."
        ) from exc


def _etat_session(affaire: dict, affaire_id: str) -> dict:
    etat_brut = session.get("etat")
    affaire_stockee = session.get("affaire_id")
    if isinstance(etat_brut, dict) and affaire_stockee == affaire_id:
        return copy.deepcopy(etat_brut)
    return nouvelle_partie(affaire)


if __name__ == "__main__":
    creer_app().run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")
