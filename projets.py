"""
Gestion des projets GEO.

Un projet = un dossier dans Telechargements portant le nom du projet,
contenant :
  - un fichier DXF par panneau
  - un fichier projet.json qui memorise les cotes saisies, pour
    pouvoir rouvrir et modifier le projet plus tard

Aucune dependance externe (json et os font partie de Python).
"""
import json
import os
from datetime import datetime


def dossier_telechargements():
    """Dossier Telechargements de l'appareil (repli : dossier maison)."""
    try:
        from android.storage import primary_external_storage_path  # type: ignore
        return os.path.join(primary_external_storage_path(), "Download")
    except Exception:
        return os.path.join(os.path.expanduser("~"), "Downloads")


def dossier_projet(nom_projet):
    return os.path.join(dossier_telechargements(), nom_projet)


def sauvegarder_projet(nom_projet, panneaux):
    """Ecrit projet.json dans le dossier du projet. Retourne le chemin."""
    dossier = dossier_projet(nom_projet)
    os.makedirs(dossier, exist_ok=True)

    donnees = {
        "nom_projet": nom_projet,
        "date_modification": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "panneaux": [
            {
                "ref": p["ref"],
                "base_type": p["base_type"],
                "base_params": p["base_params"],
                "arrondis": p.get("arrondis", []),
                "marge": p.get("marge", 0),
                "rectiligne": p.get("rectiligne", 0),
            }
            for p in panneaux
        ],
    }

    chemin = os.path.join(dossier, "projet.json")
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(donnees, f, ensure_ascii=False, indent=2)
    return chemin


def charger_projet(nom_projet):
    """Relit projet.json. Retourne la liste des panneaux, ou None."""
    chemin = os.path.join(dossier_projet(nom_projet), "projet.json")
    if not os.path.exists(chemin):
        return None
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            donnees = json.load(f)
        return donnees.get("panneaux", [])
    except Exception:
        return None


def lister_projets():
    """Liste les projets existants : [(nom, nb_panneaux, date), ...]
    tries du plus recent au plus ancien."""
    base = dossier_telechargements()
    projets = []
    if not os.path.isdir(base):
        return projets

    try:
        for nom in os.listdir(base):
            chemin_json = os.path.join(base, nom, "projet.json")
            if os.path.exists(chemin_json):
                try:
                    with open(chemin_json, "r", encoding="utf-8") as f:
                        d = json.load(f)
                    projets.append((nom, len(d.get("panneaux", [])),
                                     d.get("date_modification", "")))
                except Exception:
                    projets.append((nom, 0, ""))
    except Exception:
        pass

    projets.sort(key=lambda p: p[2], reverse=True)
    return projets


# =====================================================================
# Sauvegarde automatique du travail en cours (hors projet nomme)
# =====================================================================
def _chemin_brouillon():
    try:
        from android.storage import primary_external_storage_path  # type: ignore
        base = os.path.join(primary_external_storage_path(), "Download", ".geo")
    except Exception:
        base = os.path.join(os.path.expanduser("~"), ".geo")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "brouillon.json")


def sauvegarder_brouillon(nom_projet, panneaux):
    """Sauvegarde silencieuse du travail en cours, pour ne rien perdre
    si l'application se ferme (batterie, erreur systeme)."""
    try:
        with open(_chemin_brouillon(), "w", encoding="utf-8") as f:
            json.dump({"nom_projet": nom_projet, "panneaux": panneaux},
                      f, ensure_ascii=False)
    except Exception:
        pass


def charger_brouillon():
    """Retourne (nom_projet, panneaux) ou (None, [])."""
    try:
        chemin = _chemin_brouillon()
        if not os.path.exists(chemin):
            return None, []
        with open(chemin, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d.get("nom_projet"), d.get("panneaux", [])
    except Exception:
        return None, []


def effacer_brouillon():
    try:
        chemin = _chemin_brouillon()
        if os.path.exists(chemin):
            os.remove(chemin)
    except Exception:
        pass
