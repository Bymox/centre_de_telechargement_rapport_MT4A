# -*- coding: utf-8 -*-
"""
Analyse des fréquences RF — script final Juillet 2025 (version robuste)
But :
- calculer les plages RF susceptibles de générer des produits de mélange (m,n)
- calculer et afficher la plage de fréquence image (supradyne/infradyne)
- trier/filtrer les spurious et générer un rapport texte
Modifications apportées :
- recherche du fichier YAML dans le même dossier que le script (__file__)
- écriture du fichier TXT de sortie dans le même dossier que le script
- messages d'erreur clairs si YAML absent ou mal formé
Remarques :
- Toutes les fréquences sont en MHz.
- La convention d'indexation pour la table de puissances est expliquée dans get_puissance().
"""

from pathlib import Path
import sys
import yaml
from typing import List, Optional, Tuple

# ---------------------------
# Fonctions utilitaires
# ---------------------------

def charger_parametres_yaml(fichier_yaml: str) -> dict:
    """Charge et renvoie le contenu YAML sous forme de dict Python.
    Lève une exception si le fichier est introuvable ou invalide."""
    p = Path(fichier_yaml)
    if not p.exists():
        raise FileNotFoundError(f"Fichier YAML introuvable : {p}")
    with p.open("r", encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise RuntimeError(f"Erreur lecture YAML : {e}") from e
    if not isinstance(data, dict):
        raise ValueError("Le fichier YAML doit contenir un mapping (dictionnaire) en racine.")
    return data


def get_puissance(m: int, n: int, table: Optional[List[List]]) -> Optional[float]:
    """
    Récupère la puissance (dBc) dans la table 'puissance_spurious' pour (m,n).
    Convention d'indexation (code actuel) :
      - ligne index = abs(m) - 1  -> ligne 0 correspond à |m| == 1
      - colonne index = abs(n)    -> colonne 0 correspond à n == 0
    Exemples :
      m = -1, n = 2  -> table[0][2]
      m = 2,  n = 0  -> table[1][0]
    Retourne None si valeur absente / invalide / hors borne.
    """
    if table is None:
        return None
    im = abs(m) - 1
    in_ = abs(n)
    # vérification bornes
    if im < 0 or im >= len(table):
        return None
    # certaines lignes pourraient avoir longueur inégale -> safe check
    if in_ < 0 or in_ >= len(table[im]):
        return None
    val = table[im][in_]
    # valeurs 'ref' ou 'na' considérées comme non fournies
    if isinstance(val, str) and val.lower() in {"ref", "na"}:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ---------------------------
# Calculs principaux
# ---------------------------

def calculer_plage_image(params: dict) -> Tuple[float, float]:
    """
    Calcule la plage de fréquence image (en MHz) basée sur l'OL fixe et la bande FI.
    'from' accepte 'supradyne' (OL + FI) ou 'infradyne' (OL - FI).
    """
    OL = params["OL_fixe_MHz"]
    FI_min = params["FI_min_MHz"]
    FI_max = params["FI_max_MHz"]
    mode = params.get("from", "supradyne").lower().strip()
    if mode == "supradyne":
        return OL + FI_min, OL + FI_max
    elif mode == "infradyne":
        return OL - FI_max, OL - FI_min
    else:
        raise ValueError("Mode de conversion invalide (attendu 'supradyne' ou 'infradyne')")


def calculer_plages(params: dict) -> List[dict]:
    """
    Parcourt tous les couples (m,n) et renvoie une liste d'entrées :
      { 'm': int, 'n': int, 'type': 'utile'|'image'|'spurious'|'fuite', 'RF_min': float, 'RF_max': float }
    Explications de traitement dans les commentaires du code.
    """
    m_max = int(params["m_max"])
    n_max = int(params["n_max"])
    OL = float(params["OL_fixe_MHz"])
    FI_min, FI_max = float(params["FI_min_MHz"]), float(params["FI_max_MHz"])
    RF_min, RF_max = float(params["RF_min_MHz"]), float(params["RF_max_MHz"])
    mode = params.get("from", "supradyne").lower().strip()

    resultats: List[dict] = []

    for m in range(-m_max, m_max + 1):
        for n in range(-n_max, n_max + 1):
            # ignore le cas trivial (0,0)
            if m == 0 and n == 0:
                continue

            try:
                # CAS m == 0 => le produit ne dépend que de n*OL (fuite possible)
                if m == 0:
                    FI = abs(n * OL)
                    if not (FI_min <= FI <= FI_max):
                        continue
                    lo_c, hi_c = RF_min, RF_max

                # CAS n == 0 => FI = m * RF  => RF = FI / m
                elif n == 0:
                    lo = FI_min / abs(m)
                    hi = FI_max / abs(m)
                    lo_c = max(lo, RF_min)
                    hi_c = min(hi, RF_max)
                    if lo_c > hi_c:
                        continue

                # CAS général : résoudre m*RF + n*OL ∈ [FI_min, FI_max]
                else:
                    rf1 = (FI_min - n * OL) / m
                    rf2 = (FI_max - n * OL) / m
                    lo, hi = sorted((rf1, rf2))
                    lo_c = max(lo, RF_min)
                    hi_c = min(hi, RF_max)
                    if lo_c > hi_c:
                        continue

            except ZeroDivisionError:
                # sécurité (normalement non atteint car m == 0 géré)
                continue

            # étiquetage
            if m == 0 or n == 0:
                label = "fuite"
            elif (mode == "supradyne" and (m, n) == (-1, 1)) \
              or (mode == "infradyne" and (m, n) == (1, -1)):
                label = "utile"
            elif (mode == "supradyne" and (m, n) == (1, -1)) \
              or (mode == "infradyne" and (m, n) == (-1, 1)):
                label = "image"
            else:
                label = "spurious"

            resultats.append({
                "m":      m,
                "n":      n,
                "type":   label,
                "RF_min": round(lo_c, 2),
                "RF_max": round(hi_c, 2),
            })

    return resultats


def generer_rapport_interference(params: dict) -> List[str]:
    """
    Vérifie deux interférences simples :
      - OL dans la bande FI
      - chevauchement entre bande RF et bande FI
    Retourne une liste de lignes pour insertion dans le fichier rapport.
    """
    OL = params["OL_fixe_MHz"]
    RF_min, RF_max = params["RF_min_MHz"], params["RF_max_MHz"]
    FI_min, FI_max = params["FI_min_MHz"], params["FI_max_MHz"]

    ol_dans_fi = FI_min <= OL <= FI_max
    rf_dans_fi = not (RF_max < FI_min or RF_min > FI_max)

    lignes = []
    lignes.append("=== Vérification des fuites directes ===")
    if ol_dans_fi:
        lignes.append("❌ L'OL est DANS la bande FI → ⚠️ PROBLÈME")
    else:
        lignes.append("✅ L'OL est HORS de la bande FI")
    if rf_dans_fi:
        lignes.append("❌ Une partie de la bande RF est DANS la bande FI → ⚠️ PROBLÈME")
    else:
        lignes.append("✅ La bande RF est HORS de la bande FI")
    lignes.append("")
    return lignes


# ---------------------------
# Génération du rapport
# ---------------------------

def sauvegarder_rapport(resultats: List[dict], fichier: str, params: dict, table_puiss=None, plage_image=None) -> None:
    """
    Génère le rapport texte final 'fichier'.
    Tri :
      - si table_puiss fournie : tri d'abord par puissance si disponible (valeur numérique plus petite = prioritaire),
        sinon par complexité (|m|+|n|).
      - sinon : tri par complexité.
    Format d'écriture humain lisible.
    """
    sections = {"utile": [], "image": [], "spurious": [], "fuite": []}
    for r in resultats:
        sections[r["type"]].append(r)

    sp = sections["spurious"]

    if table_puiss is not None:
        # tri en combinant puissance (si dispo) puis complexité
        def key_fn(x):
            p = get_puissance(x["m"], x["n"], table_puiss)
            p_key = p if p is not None else float('inf')
            return (p_key, abs(x["m"]) + abs(x["n"]), abs(x["m"]), abs(x["n"]), x["RF_min"])
        sp.sort(key=key_fn)
    else:
        sp.sort(key=lambda x: (abs(x["m"]) + abs(x["n"]), abs(x["m"]), abs(x["n"]), x["RF_min"]))

    # écriture sécurisée du fichier (créera/écrasera)
    p_out = Path(fichier)
    try:
        with p_out.open("w", encoding="utf-8") as f:
            # Interférences directes OL/FI et RF/FI
            interferences = generer_rapport_interference(params)
            for ligne in interferences:
                f.write(ligne + "\n")

            # Fréquences utiles
            f.write("=== Fréquences utiles ===\n")
            f.write(f"Nombre total : {len(sections['utile'])}\n")
            f.write("m,   n,  RF_min (MHz),  RF_max (MHz)\n")
            for u in sections["utile"]:
                f.write(f"{u['m']:3d}, {u['n']:3d}, {u['RF_min']:12.1f}, {u['RF_max']:12.1f}\n")
            f.write("\n")

            # Fréquences images
            f.write("=== Fréquences images ===\n")
            f.write("Plage de fréquence image (MHz) : \n")
            if plage_image:
                f.write(f"{plage_image[0]:8.2f}, {plage_image[1]:8.2f} \n\n")
            else:
                f.write("N/A, N/A\n\n")

            # Spurious
            f.write("=== Spurious complexes (triés) ===\n")
            f.write(f"Nombre total : {len(sp)}\n")
            f.write("m,   n,  RF_min (MHz),  RF_max (MHz), Puissance (dBc)\n")
            for s in sp:
                pwr = get_puissance(s['m'], s['n'], table_puiss) if table_puiss is not None else None
                pwr_str = f"{pwr:.1f}" if pwr is not None else ""
                f.write(f"{s['m']:3d}, {s['n']:3d}, {s['RF_min']:12.1f}, {s['RF_max']:12.1f},       {pwr_str:15}\n")
            f.write("\n")
    except OSError as e:
        raise RuntimeError(f"Impossible d'écrire le fichier de sortie '{p_out}': {e}") from e


# ---------------------------
# Entrée du script
# ---------------------------

if __name__ == "__main__":
    # Détermine le dossier du script (même si on exécute depuis un autre cwd).
    # Si __file__ non défini (rare dans REPL), on prend le cwd actuel.
    try:
        script_path = Path(__file__).resolve()
        dossier_script = script_path.parent
    except NameError:
        dossier_script = Path.cwd()

    # chemins fixes dans le dossier du script
    fichier_yaml = dossier_script / "parametres_spurious.yaml"
    fichier_txt = dossier_script / "Spurious_results.txt"

    # Chargement YAML avec gestion d'erreur claire
    try:
        params = charger_parametres_yaml(str(fichier_yaml))
    except FileNotFoundError:
        print(f"[ERREUR] Fichier de paramètres introuvable : {fichier_yaml}")
        print("Place le fichier 'parametres_spurious.yaml' dans le même dossier que ce script.")
        sys.exit(2)
    except Exception as e:
        print(f"[ERREUR] Impossible de charger le YAML : {e}")
        sys.exit(3)

    # Calculs
    try:
        resultats = calculer_plages(params)
        # calcule toujours la plage image (même si hors RF)
        plage_img = calculer_plage_image(params)
    except Exception as e:
        print(f"[ERREUR] Problème lors des calculs : {e}")
        sys.exit(4)

    tab_puiss = params.get("puissance_spurious")

    # écriture du rapport (dans le même dossier que le script)
    try:
        sauvegarder_rapport(resultats, str(fichier_txt), params, tab_puiss, plage_img)
        print(f"[OK] Rapport généré : {fichier_txt}")
    except Exception as e:
        print(f"[ERREUR] Écriture du rapport échouée : {e}")
        sys.exit(5)
