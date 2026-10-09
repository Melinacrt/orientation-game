"""Chargement et validation d'une affaire (format ``data/format-affaire.json``).

Le jeu fonctionne sans IA : ce module se contente de lire un JSON et de
vérifier sa cohérence structurelle. Toute erreur est signalée par une
``ValueError`` au message rédigé en français, jamais par une traceback brute.
"""

import json
import re
from pathlib import Path

TRAITS_AUTORISES = frozenset({"analyser", "convaincre", "enqueter", "aider", "proteger"})

MOTIF_IMAGE = re.compile(r"^img/[a-z0-9\-_/]+\.(png|jpg|jpeg|webp|svg)$")
LONGUEUR_MAX_IMAGE = 200
MOTIF_THEME = re.compile(r"^[a-z0-9-]+$")

CLES_OBLIGATOIRES = ("id", "metier", "titre", "contexte", "debut", "etapes", "fins")


def charger_affaire(chemin: str | Path) -> dict:
    """Charge une affaire depuis un fichier JSON et valide sa structure.

    Args:
        chemin: Chemin (``str`` ou ``pathlib.Path``) vers le fichier JSON.

    Returns:
        Le dictionnaire de l'affaire dont la structure a été validée.

    Raises:
        ValueError: Si le fichier est introuvable, si le JSON est malformé ou
            si la structure ne respecte pas le format attendu.
    """
    fichier = _vers_chemin(chemin)

    try:
        contenu = fichier.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"Fichier d'affaire introuvable : {fichier}") from exc
    except OSError as exc:
        raise ValueError(f"Impossible de lire le fichier d'affaire : {exc}") from exc

    try:
        affaire = json.loads(contenu)
    except json.JSONDecodeError as exc:
        message = f"JSON malformé dans {fichier.name} : {exc.msg} "
        message += f"(ligne {exc.lineno}, colonne {exc.colno})."
        raise ValueError(message) from exc

    _valider_structure(affaire)
    return affaire


def compter_etapes(affaire: dict) -> int:
    """Compte le nombre d'étapes d'une affaire.

    Args:
        affaire: Dictionnaire de l'affaire déjà chargée.

    Returns:
        Le nombre d'entrées de ``affaire["etapes"]``.

    Raises:
        ValueError: Si l'entrée est invalide (pas un dictionnaire, ou
            clé « etapes » absente, non-dict ou vide).
    """
    if not isinstance(affaire, dict):
        raise ValueError("L'affaire doit être un objet JSON.")
    etapes = affaire.get("etapes")
    if not isinstance(etapes, dict) or not etapes:
        raise ValueError("La clé « etapes » doit être un objet JSON non vide.")
    return len(etapes)


def _vers_chemin(chemin: str | Path) -> Path:
    if isinstance(chemin, Path):
        return chemin
    if isinstance(chemin, str):
        if not chemin.strip():
            raise ValueError("Le chemin fourni est vide.")
        return Path(chemin)
    raise ValueError("Le chemin doit être une chaîne de caractères ou un pathlib.Path.")


def _valider_structure(affaire: object) -> None:
    if not isinstance(affaire, dict):
        raise ValueError("L'affaire doit être un objet JSON.")

    manquantes = [cle for cle in CLES_OBLIGATOIRES if cle not in affaire]
    if manquantes:
        raise ValueError(f"Clés obligatoires manquantes : {', '.join(manquantes)}.")

    for cle in ("id", "metier", "titre", "contexte"):
        if not _est_texte_non_vide(affaire[cle]):
            raise ValueError(f"La clé « {cle} » doit être une chaîne non vide.")

    _valider_theme(affaire.get("theme"))

    etapes = affaire["etapes"]
    if not isinstance(etapes, dict) or not etapes:
        raise ValueError("La clé « etapes » doit être un objet JSON non vide.")

    for identifiant, etape in etapes.items():
        _valider_etape(identifiant, etape, etapes)

    if not isinstance(affaire["debut"], str) or affaire["debut"] not in etapes:
        raise ValueError("La clé « debut » doit référencer une étape existante.")

    fins = affaire["fins"]
    if not isinstance(fins, list) or not fins:
        raise ValueError("La clé « fins » doit être une liste non vide.")

    for fin in fins:
        _valider_fin(fin)


def _valider_theme(theme: object) -> None:
    """Valide le champ optionnel ``theme`` d'une affaire.

    Une affaire sans ``theme`` reste valide (optionnel non durci). Si
    ``theme`` est présent, il doit être une chaîne non vide en minuscules,
    chiffres et tirets uniquement (ex. « cyber »), utilisée pour habiller
    la partie et le bilan.
    """
    if theme is None:
        return
    if (
        not isinstance(theme, str)
        or not theme.strip()
        or not MOTIF_THEME.match(theme)
    ):
        raise ValueError(
            "La clé « theme » doit être une chaîne non vide en minuscules, "
            "chiffres et tirets uniquement (ex. « cyber »)."
        )


def _valider_etape(identifiant: str, etape: object, etapes: dict) -> None:
    if not isinstance(etape, dict):
        raise ValueError(f"L'étape « {identifiant} » doit être un objet JSON.")

    if not _est_texte_non_vide(etape.get("texte")):
        raise ValueError(f"L'étape « {identifiant} » doit avoir un « texte » non vide.")

    choix_liste = etape.get("choix")
    if not isinstance(choix_liste, list) or not choix_liste:
        raise ValueError(f"L'étape « {identifiant} » doit avoir une liste « choix » non vide.")

    for choix in choix_liste:
        _valider_choix(identifiant, choix, etapes)

    _valider_image(identifiant, etape)


def _valider_image(identifiant: str, etape: dict) -> None:
    """Valide les champs optionnels ``image`` / ``image_alt`` d'une étape.

    Une étape sans ``image`` reste valide (optionnel non durci). Si ``image``
    est présente, elle doit être un chemin relatif sous ``img/`` (minuscules,
    chiffres, tirets, extensions autorisées, 200 caractères maximum, sans
    ``..`` ni URL) et ``image_alt`` doit être un texte alternatif non vide.
    """
    image = etape.get("image")
    alt = etape.get("image_alt")
    if image is None:
        if alt is not None:
            raise ValueError(
                f"L'étape « {identifiant} » a un « image_alt » sans « image »."
            )
        return
    if (
        not isinstance(image, str)
        or not image.strip()
        or len(image) > LONGUEUR_MAX_IMAGE
        or ".." in image
        or "\\" in image
        or image.startswith(("/", "http"))
        or not MOTIF_IMAGE.match(image)
    ):
        raise ValueError(
            f"L'étape « {identifiant} » a une « image » invalide : chemin relatif "
            "attendu sous « img/ » (minuscules, chiffres, tirets, extension "
            "png/jpg/jpeg/webp/svg, 200 caractères maximum, sans « .. » ni URL)."
        )
    if not isinstance(alt, str) or not alt.strip():
        raise ValueError(
            f"L'étape « {identifiant} » a une « image » sans « image_alt » "
            "non vide : chaque image doit avoir un texte alternatif."
        )


def _valider_choix(etape_id: str, choix: object, etapes: dict) -> None:
    if not isinstance(choix, dict):
        raise ValueError(f"Un choix de l'étape « {etape_id} » doit être un objet JSON.")

    for cle in ("id", "label"):
        if not _est_texte_non_vide(choix.get(cle)):
            raise ValueError(
                f"Choix de l'étape « {etape_id} » : « {cle} » doit être une chaîne non vide."
            )

    traits = choix.get("traits")
    if not isinstance(traits, dict):
        raise ValueError(
            f"Les « traits » d'un choix de l'étape « {etape_id} » doivent être un objet JSON."
        )
    for trait, points in traits.items():
        if trait not in TRAITS_AUTORISES:
            autorises = ", ".join(sorted(TRAITS_AUTORISES))
            raise ValueError(f"Trait non autorisé « {trait} » (autorisés : {autorises}).")
        if not _est_entier(points):
            raise ValueError(f"Le score du trait « {trait} » doit être un entier.")

    gravite = choix.get("gravite")
    if not _est_entier(gravite):
        raise ValueError(
            f"La « gravite » du choix de l'étape « {etape_id} » doit être un entier."
        )
    if gravite < 0:
        raise ValueError(f"La « gravite » du choix de l'étape « {etape_id} » doit être >= 0.")

    suite = choix.get("suite")
    if suite is not None and suite not in etapes:
        raise ValueError(
            f"La « suite » d'un choix de l'étape « {etape_id} » doit référencer une étape "
            "existante ou être nulle."
        )


def _valider_fin(fin: object) -> None:
    if not isinstance(fin, dict):
        raise ValueError("Chaque fin doit être un objet JSON.")

    for cle in ("gravite_max", "titre"):
        if cle not in fin:
            raise ValueError(f"Une fin doit contenir la clé « {cle} ».")

    if not _est_entier(fin["gravite_max"]):
        raise ValueError("Le « gravite_max » d'une fin doit être un entier.")


def _est_texte_non_vide(valeur: object) -> bool:
    return isinstance(valeur, str) and bool(valeur.strip())


def _est_entier(valeur: object) -> bool:
    return isinstance(valeur, int) and not isinstance(valeur, bool)
