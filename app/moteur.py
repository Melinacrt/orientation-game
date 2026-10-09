"""Moteur de partie du jeu Orientation Game (sans IA).

Une partie se joue à partir d'une affaire déjà validée : cumul des points
par trait, cumul de la gravité, avancée d'étape en étape via ``suite``,
puis bilan qui cite les vrais choix du joueur. Toute entrée invalide
est signalée par une ``ValueError`` au message rédigé en français.
"""

import json
from pathlib import Path

TRAITS = ("analyser", "convaincre", "enqueter", "aider", "proteger")

_LONGUEUR_MAX_ID = 200

_MACHINES_INITIALES = 1
_MACHINES_MAX = 50
_CONFIANCE_INITIALE = 80
_CONFIANCE_GAIN_PAR_POINT = 5
_CONFIANCE_PERTE_PAR_GRAVITE = 10
_CONFIANCE_MIN = 0
_CONFIANCE_MAX = 100
_TEMPS_BUDGET_MINUTES = 120
_TEMPS_COUT_PAR_COUP = 15
_SOLIDITE_INITIALE = 10
_SOLIDITE_MAX = 20
_SOLIDITE_PERTE_PAR_GRAVITE = 2

_TITRES_PROFILS_AVOCAT = frozenset(
    {
        "Stratège du dossier",
        "Orateur de l'audience",
        "Enquêteur du contradictoire",
        "Défenseur à l'écoute",
        "Gardien des droits",
    }
)


def _est_affaire_avocat(affaire: object) -> bool:
    """Indique si une affaire relève du métier avocat (thème tribunal)."""
    if not isinstance(affaire, dict):
        return False
    return affaire.get("metier") == "avocat" or affaire.get("theme") == "avocat"


def _est_profil_avocat(profil: object) -> bool:
    """Indique si un profil appartient au métier avocat (id ou titre)."""
    if not isinstance(profil, dict):
        return False
    identifiant = profil.get("id", "")
    if isinstance(identifiant, str) and identifiant.startswith("avocat-"):
        return True
    return profil.get("titre") in _TITRES_PROFILS_AVOCAT


def _profils_du_metier(affaire: dict, profils: list) -> list:
    """Restreint les profils au métier de l'affaire jouée (repli : tous).

    Une affaire d'avocat est évaluée avec les seuls profils avocat, une
    affaire cyber avec les seuls profils cyber. Si le filtrage ne garde
    aucun profil (listes personnalisées des tests), la liste complète
    est conservée : le comportement historique reste inchangé.
    """
    metier = affaire.get("metier") if isinstance(affaire, dict) else None
    if metier == "avocat":
        restreints = [p for p in profils if _est_profil_avocat(p)]
        if restreints:
            return restreints
    elif metier == "cyber":
        restreints = [p for p in profils if not _est_profil_avocat(p)]
        if restreints:
            return restreints
    return list(profils)


def _tableau_avocat(etat: dict) -> dict:
    """Tableau de bord de l'affaire avocat (fonction pure, sans IA).

    Formule déterministe (état -> valeurs) :
    - ``confiance`` (Confiance d'Inès) = 80 + 5 × (convaincre + aider)
      − 10 × gravité, borné entre 0 et 100 (80 au départ).
    - ``solidite`` (Solidité du dossier) = 10 + (analyser + enqueter)
      − 2 × gravité, borné entre 0 et 20 (10 au départ).
    - ``temps`` (Temps avant l'audience) = max(0, 120 − 15 × nb_coups)
      en minutes (budget fictif, distinct du chronomètre temps réel).
    """
    if not isinstance(etat, dict):
        etat = {}
    gravite = etat.get("gravite", 0)
    if isinstance(gravite, bool) or not isinstance(gravite, int) or gravite < 0:
        gravite = 0
    scores = etat.get("scores", {})
    if not isinstance(scores, dict):
        scores = {}

    def _points(trait: str) -> int:
        valeur = scores.get(trait, 0)
        if isinstance(valeur, bool) or not isinstance(valeur, int):
            return 0
        return valeur

    convaincre = _points("convaincre")
    aider = _points("aider")
    analyser = _points("analyser")
    enqueter = _points("enqueter")
    historique = etat.get("historique", [])
    nb_coups = len(historique) if isinstance(historique, list) else 0
    confiance = _CONFIANCE_INITIALE
    confiance += _CONFIANCE_GAIN_PAR_POINT * (convaincre + aider)
    confiance -= _CONFIANCE_PERTE_PAR_GRAVITE * gravite
    confiance = max(_CONFIANCE_MIN, min(_CONFIANCE_MAX, confiance))
    solidite = _SOLIDITE_INITIALE + (analyser + enqueter)
    solidite -= _SOLIDITE_PERTE_PAR_GRAVITE * gravite
    solidite = max(0, min(_SOLIDITE_MAX, solidite))
    temps = max(0, _TEMPS_BUDGET_MINUTES - _TEMPS_COUT_PAR_COUP * nb_coups)
    return {
        "confiance": confiance,
        "solidite": solidite,
        "temps": temps,
    }


def tableau_de_bord(affaire: dict, etat: dict) -> dict:
    """Calcule le tableau de bord de la partie (fonction pure, sans IA).

    Formule cyber (affaires cyber ou sans métier avocat, historique) :
    - ``machines_infectees`` = min(1 + gravité, 50) (1 au départ, borné à 50).
    - ``confiance_direction`` = 80 + 5 × (convaincre + aider) − 10 × gravité,
      borné entre 0 et 100 (80 au départ).
    - ``temps_restant`` = max(0, 120 − 15 × nb_coups) en minutes (budget fictif,
      distinct du chronomètre temps réel).

    Formule avocat (``affaire["metier"]`` ou ``affaire["theme"]`` vaut
    ``"avocat"``, ambiance tribunal) :
    - ``confiance`` (Confiance d'Inès) = 80 + 5 × (convaincre + aider)
      − 10 × gravité, borné entre 0 et 100 (80 au départ).
    - ``solidite`` (Solidité du dossier) = 10 + (analyser + enqueter)
      − 2 × gravité, borné entre 0 et 20 (10 au départ).
    - ``temps`` (Temps avant l'audience) = max(0, 120 − 15 × nb_coups).

    Args:
        affaire: Dictionnaire de l'affaire (le métier ou le thème décide
            de la formule ; toute autre affaire garde la formule cyber).
        etat: État de la partie (``gravite``, ``scores``, ``historique``).

    Returns:
        Le dictionnaire du tableau de bord aux valeurs entières bornées.
    """
    if _est_affaire_avocat(affaire):
        return _tableau_avocat(etat)
    if not isinstance(etat, dict):
        etat = {}
    gravite = etat.get("gravite", 0)
    if isinstance(gravite, bool) or not isinstance(gravite, int) or gravite < 0:
        gravite = 0
    scores = etat.get("scores", {})
    if not isinstance(scores, dict):
        scores = {}
    convaincre = scores.get("convaincre", 0)
    aider = scores.get("aider", 0)
    if isinstance(convaincre, bool) or not isinstance(convaincre, int):
        convaincre = 0
    if isinstance(aider, bool) or not isinstance(aider, int):
        aider = 0
    historique = etat.get("historique", [])
    nb_coups = len(historique) if isinstance(historique, list) else 0
    machines = min(_MACHINES_INITIALES + gravite, _MACHINES_MAX)
    confiance = _CONFIANCE_INITIALE
    confiance += _CONFIANCE_GAIN_PAR_POINT * (convaincre + aider)
    confiance -= _CONFIANCE_PERTE_PAR_GRAVITE * gravite
    confiance = max(_CONFIANCE_MIN, min(_CONFIANCE_MAX, confiance))
    temps = max(0, _TEMPS_BUDGET_MINUTES - _TEMPS_COUT_PAR_COUP * nb_coups)
    return {
        "machines_infectees": machines,
        "confiance_direction": confiance,
        "temps_restant": temps,
    }


def nouvelle_partie(affaire: dict) -> dict:
    """Crée l'état initial d'une partie pour une affaire donnée.

    Args:
        affaire: Dictionnaire de l'affaire (doit contenir ``debut``,
            ``etapes`` et ``fins`` cohérents).

    Returns:
        Un état ``{"scores", "gravite", "historique", "etape_courante"}``
        avec les 5 traits à 0, une gravité à 0, un historique vide et
        l'étape courante positionnée sur ``debut``.

    Raises:
        ValueError: Si l'affaire est invalide.
    """
    _valider_affaire(affaire)
    return {
        "scores": {trait: 0 for trait in TRAITS},
        "gravite": 0,
        "historique": [],
        "etape_courante": affaire["debut"],
    }


def jouer_coup(affaire: dict, etat: dict, etape_id: str, choix_id: str) -> dict:
    """Joue un choix du joueur et fait avancer l'état de la partie.

    Args:
        affaire: Dictionnaire de l'affaire en cours.
        etat: État courant de la partie (modifié en place et renvoyé).
        etape_id: Identifiant de l'étape jouée (chaîne non vide ≤ 200).
        choix_id: Identifiant du choix retenu (chaîne non vide ≤ 200).

    Returns:
        L'état mis à jour (scores et gravité cumulés, historique enrichi
        d'une entrée ``{"etape", "choix", "label", "consequence"}``,
        ``etape_courante`` avancée vers ``suite`` ou ``None`` si terminé).

    Raises:
        ValueError: Si un identifiant est invalide (type, vide, trop long)
            ou si l'étape / le choix n'existe pas dans l'affaire.
    """
    _valider_affaire(affaire)
    _valider_etat(etat)
    _exiger_identifiant(etape_id, "etape")
    _exiger_identifiant(choix_id, "choix")

    etapes = affaire["etapes"]
    if etape_id not in etapes:
        raise ValueError(f"L'étape « {etape_id} » n'existe pas dans cette affaire.")
    etape = etapes[etape_id]
    choix = _trouver_choix(etape_id, etape, choix_id)

    traits = choix.get("traits", {})
    if not isinstance(traits, dict):
        raise ValueError("Les traits du choix doivent être un objet.")
    gravite = choix.get("gravite", 0)
    if isinstance(gravite, bool) or not isinstance(gravite, int) or gravite < 0:
        raise ValueError("La gravité du choix doit être un entier positif ou nul.")

    scores = etat["scores"]
    suite = choix.get("suite")
    if suite is not None and suite not in etapes:
        raise ValueError(
            f"La suite « {suite} » du choix « {choix_id} » n'existe pas."
        )
    for trait, points in traits.items():
        if trait not in TRAITS:
            raise ValueError(f"Le trait « {trait} » n'existe pas dans cette affaire.")
        if isinstance(points, bool) or not isinstance(points, int):
            raise ValueError(f"Le score du trait « {trait} » doit être un entier.")
        scores[trait] = int(scores.get(trait, 0)) + points
    etat["gravite"] = int(etat["gravite"]) + gravite

    label = choix.get("label", "")
    consequence = choix.get("consequence", "")
    etat["historique"].append(
        {
            "etape": etape_id,
            "choix": choix_id,
            "label": label,
            "consequence": consequence,
        }
    )

    if suite is None:
        etat["etape_courante"] = None
    else:
        etat["etape_courante"] = suite
    return etat


def calculer_bilan(affaire: dict, etat: dict, profils: object) -> dict:
    """Calcule le bilan d'une partie à partir de l'historique réel.

    Args:
        affaire: Dictionnaire de l'affaire jouée.
        etat: État de la partie (scores, gravité, historique).
        profils: Liste de profils (dicts avec ``traits_dominants``,
            ``titre``, ``texte`` et ``metiers_proches`` ou ``metiers``
            enrichis : noms + phrase de lien + statut jouable), ou chemin
            (``str`` / ``Path``) vers un fichier JSON contenant une telle liste.

    Returns:
        Un dictionnaire ``{"scores", "gravite", "fin", "citations",
        "profil", "metiers_proches", "metiers_details",
        "traits_dominants", "gravite_max", "niveau_gravite"}`` où ``fin``
        est la première fin dont ``gravite_max`` couvre la gravité,
        ``citations`` reprend les labels et conséquences réellement
        choisis, ``profil`` est le profil du métier de l'affaire jouée
        (avocat ou cyber) dont les traits dominants
        scorent le mieux (ex æquo : le premier), ``metiers_proches``
        reste la liste des noms (compatibilité), ``metiers_details``
        porte les phrases de lien et le statut jouable, et
        ``traits_dominants`` donne le top 2 des traits du joueur
        (ex æquo : premier rencontré dans l'ordre des traits).

    Raises:
        ValueError: Si l'affaire, l'état ou les profils sont invalides.
    """
    _valider_affaire(affaire)
    _valider_etat(etat)
    liste_profils = _profils_du_metier(affaire, _charger_profils(profils))

    gravite = int(etat["gravite"])
    fin = _choisir_fin(affaire["fins"], gravite)

    citations: list[str] = []
    for entree in etat["historique"]:
        label = entree.get("label", "")
        if isinstance(label, str) and label.strip():
            citations.append(label)
        consequence = entree.get("consequence", "")
        if isinstance(consequence, str) and consequence.strip():
            citations.append(consequence)

    scores = dict(etat["scores"])
    profil = _choisir_profil(liste_profils, scores)

    return {
        "scores": scores,
        "gravite": gravite,
        "fin": fin,
        "citations": citations,
        "profil": profil,
        "metiers_proches": _noms_metiers(profil),
        "metiers_details": _details_metiers(profil),
        "traits_dominants": _top_traits(scores, nombre=2),
        "gravite_max": _gravite_max(affaire["fins"]),
        "niveau_gravite": _niveau_gravite(gravite),
    }


def _exiger_identifiant(valeur: object, nom: str) -> None:
    if not isinstance(valeur, str):
        raise ValueError(f"L'identifiant « {nom} » doit être une chaîne de caractères.")
    if not valeur.strip():
        raise ValueError(f"L'identifiant « {nom} » doit être une chaîne non vide.")
    if len(valeur) > _LONGUEUR_MAX_ID:
        raise ValueError(
            f"L'identifiant « {nom} » ne doit pas dépasser "
            f"{_LONGUEUR_MAX_ID} caractères."
        )


def _valider_affaire(affaire: object) -> None:
    if not isinstance(affaire, dict):
        raise ValueError("L'affaire doit être un objet JSON.")
    etapes = affaire.get("etapes")
    if not isinstance(etapes, dict) or not etapes:
        raise ValueError("L'affaire est invalide : la clé « etapes » est manquante.")
    debut = affaire.get("debut")
    if not isinstance(debut, str) or not debut.strip():
        raise ValueError("L'affaire est invalide : la clé « debut » est manquante.")
    if debut not in etapes:
        raise ValueError("L'affaire est invalide : « debut » ne référence aucune étape.")
    fins = affaire.get("fins")
    if not isinstance(fins, list) or not fins:
        raise ValueError("L'affaire est invalide : la clé « fins » est manquante.")


def _valider_etat(etat: object) -> None:
    if not isinstance(etat, dict):
        raise ValueError("L'état de la partie doit être un objet.")
    scores = etat.get("scores")
    if not isinstance(scores, dict):
        raise ValueError("L'état de la partie est invalide : scores manquants.")
    gravite = etat.get("gravite")
    if isinstance(gravite, bool) or not isinstance(gravite, int):
        raise ValueError("L'état de la partie est invalide : gravité manquante.")
    if not isinstance(etat.get("historique"), list):
        raise ValueError("L'état de la partie est invalide : historique manquant.")
    courante = etat.get("etape_courante")
    if courante is not None and not isinstance(courante, str):
        raise ValueError("L'état de la partie est invalide : étape courante incorrecte.")


def _trouver_choix(etape_id: str, etape: object, choix_id: str) -> dict:
    if not isinstance(etape, dict):
        raise ValueError(f"L'étape « {etape_id} » est invalide.")
    liste = etape.get("choix")
    if not isinstance(liste, list) or not liste:
        raise ValueError(f"L'étape « {etape_id} » ne propose aucun choix.")
    for choix in liste:
        if isinstance(choix, dict) and choix.get("id") == choix_id:
            return choix
    raise ValueError(
        f"Le choix « {choix_id} » n'existe pas dans l'étape « {etape_id} »."
    )


def _choisir_fin(fins: list, gravite: int) -> dict:
    for fin in fins:
        if isinstance(fin, dict) and isinstance(fin.get("gravite_max"), int):
            if not isinstance(fin["gravite_max"], bool) and gravite <= fin["gravite_max"]:
                return fin
    derniere = fins[-1]
    if not isinstance(derniere, dict):
        raise ValueError("L'affaire est invalide : les fins sont illisibles.")
    return derniere


def _charger_profils(profils: object) -> list:
    if isinstance(profils, (str, Path)):
        chemin = Path(profils) if isinstance(profils, str) else profils
        if str(chemin).strip() == "":
            raise ValueError("Le chemin des profils est vide.")
        try:
            contenu = chemin.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"Impossible de lire les profils : {exc}") from exc
        try:
            donnees = json.loads(contenu)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Les profils sont illisibles : {exc.msg}.") from exc
        if isinstance(donnees, dict) and isinstance(donnees.get("profils"), list):
            donnees = donnees["profils"]
        return _valider_liste_profils(donnees)
    if isinstance(profils, dict):
        return _valider_liste_profils([profils])
    return _valider_liste_profils(profils)


def _valider_liste_profils(profils: object) -> list:
    if not isinstance(profils, list) or not profils:
        raise ValueError("La liste des profils ne doit pas être vide.")
    for profil in profils:
        if not isinstance(profil, dict):
            raise ValueError("Chaque profil doit être un objet.")
        dominants = profil.get("traits_dominants")
        if not isinstance(dominants, list) or not dominants:
            raise ValueError("Chaque profil doit avoir des « traits_dominants ».")
        for trait in dominants:
            if trait not in TRAITS:
                raise ValueError(f"Trait dominant inconnu : « {trait} ».")
        metiers = profil.get("metiers", profil.get("metiers_proches"))
        if not isinstance(metiers, list) or not metiers:
            raise ValueError("Chaque profil doit avoir des « metiers_proches ».")
        for entree in metiers:
            _valider_entree_metier(entree)
    return list(profils)


def _valider_entree_metier(entree: object) -> None:
    """Valide une entrée métier (chaîne simple ou dict enrichi)."""
    if isinstance(entree, str):
        if not entree.strip():
            raise ValueError("Chaque métier proche doit avoir un nom non vide.")
        return
    if not isinstance(entree, dict):
        raise ValueError("Chaque métier proche doit être un nom ou un objet.")
    nom = entree.get("nom", entree.get("nom_metier", entree.get("titre", "")))
    if not isinstance(nom, str) or not nom.strip():
        raise ValueError("Chaque métier proche doit avoir un nom non vide.")


def _choisir_profil(profils: list, scores: dict) -> dict:
    meilleur = profils[0]
    meilleur_score = _score_profil(meilleur, scores)
    for profil in profils[1:]:
        score = _score_profil(profil, scores)
        if score > meilleur_score:
            meilleur = profil
            meilleur_score = score
    return meilleur


def _score_profil(profil: dict, scores: dict) -> int:
    total = 0
    for trait in profil.get("traits_dominants", []):
        valeur = scores.get(trait, 0)
        if isinstance(valeur, int) and not isinstance(valeur, bool):
            total += valeur
    return total


def _liste_metiers_brute(profil: dict) -> list:
    """Renvoie les métiers bruts (clé ``metiers`` ou ``metiers_proches``)."""
    metiers = profil.get("metiers", profil.get("metiers_proches", []))
    return list(metiers) if isinstance(metiers, list) else []


def _nom_entree_metier(entree: object) -> str:
    if isinstance(entree, str):
        return entree
    if isinstance(entree, dict):
        nom = entree.get("nom", entree.get("nom_metier", entree.get("titre", "")))
        return nom if isinstance(nom, str) else ""
    return ""


def _noms_metiers(profil: dict) -> list:
    """Noms des métiers proches (compatibilité : liste de chaînes)."""
    return [_nom_entree_metier(entree) for entree in _liste_metiers_brute(profil)]


def _details_metiers(profil: dict) -> list:
    """Détails enrichis : nom + phrase de lien + statut jouable."""
    details = []
    for entree in _liste_metiers_brute(profil):
        nom = _nom_entree_metier(entree)
        if isinstance(entree, dict):
            lien = entree.get("lien", entree.get("pourquoi", entree.get("lien_profil", "")))
            if "jouable" in entree:
                jouable = entree["jouable"]
            else:
                jouable = entree.get("disponible")
            if not isinstance(jouable, bool):
                jouable = nom.strip().lower() == "expert cyber"
            if not isinstance(lien, str):
                lien = ""
        else:
            lien = ""
            jouable = nom.strip().lower() == "expert cyber"
        details.append({"nom": nom, "lien": lien, "jouable": jouable})
    return details


def _top_traits(scores: dict, nombre: int = 2) -> list:
    """Top ``nombre`` traits par score (ex æquo : premier rencontré)."""
    ranges = sorted(TRAITS, key=lambda trait: (-int(scores.get(trait, 0)), TRAITS.index(trait)))
    return list(ranges[:nombre])


def _gravite_max(fins: list) -> int:
    valeurs = [
        fin["gravite_max"]
        for fin in fins
        if isinstance(fin, dict)
        and isinstance(fin.get("gravite_max"), int)
        and not isinstance(fin.get("gravite_max"), bool)
    ]
    return max(valeurs) if valeurs else 0


def _niveau_gravite(gravite: int) -> str:
    """Libellé lisible du niveau de gravité (mêmes seuils que les fins)."""
    if gravite <= 2:
        return "Impact maîtrisé"
    if gravite <= 6:
        return "Impact limité"
    return "Impact élevé"
