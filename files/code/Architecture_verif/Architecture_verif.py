# -*- coding: utf-8 -*-
"""
Script d'analyse rapide d'une chaîne RF décrite en YAML.
- calcule NF total (Loi de Friis)
- calcule OP1dB de sortie (combinaison en linéaire)
- affiche un résumé coloré en console

Conventions attendues pour le YAML (exemple) :
architecture:
  - name: "LNA1"
    type: "ampli"
    gain_dB: 15                 # gain nominal (dB)
    gain_dB_max: 17             # (optionnel) gain max si different
    nf_dB: 2.0                  # (optionnel) figure de bruit (dB)
    op1db_dBm: 5                # (optionnel) OP1dB en dBm
  - name: "Filt1"
    type: "filter"
    insertion_loss_dB: 2.5      # pour les filtres on fournit la perte (positive)
    # ...
Attention :
- Les unités : gains et pertes en dB, NF en dB, OP1dB en dBm.
- Le code convertit en linéaire pour les calculs (rapports linéaires, puissances en mW).
- Valeurs manquantes ont des comportements par défaut (voir build_chain).
"""

import yaml
import math
import os
from colorama import init, Fore, Back, Style

# Active colorama (réinitialisation automatique des styles après chaque print)
init(autoreset=True)

# Couleurs pour affichage par type d'étage (simple mapping visuel)
# - 'ampli'  : rouge
# - 'filter' : cyan
# - 'atten'  : jaune
# - 'switch' : vert
# - 'mixer'  : magenta
TYPE_COLORS = {
    'ampli':   Fore.RED + Style.BRIGHT,
    'filter':  Fore.CYAN + Style.BRIGHT,
    'atten':   Fore.YELLOW + Style.BRIGHT,
    'switch':  Fore.GREEN + Style.BRIGHT,
    'mixer':   Fore.MAGENTA + Style.BRIGHT,
}

# ---------- Fonctions utilitaires (conversion dB <-> linéaire) ----------

def db_to_lin(db):
    """
    Convertit une valeur en dB vers une valeur linéaire (facteur ou mW selon le contexte).
    - entrée : valeur en dB (ou dBm si contexte puissance)
    - sortie : 10^(db/10)

    Exemple :
      10 dB  -> 10
      -3 dB  -> 0.5
      0 dBm  -> 1 mW  (utilisé pour convertir dBm -> mW)
    Attention : appeler cette fonction sur des valeurs très grandes (ex : 1000) produit des floats très grands.
    """
    return 10 ** (db / 10)


def lin_to_db(lin):
    """
    Convertit une valeur linéaire vers dB.
    - si lin est un ratio (ex : gain linéaire) la sortie est en dB.
    - si lin est en mW, la sortie est en dBm (0 dBm => 1 mW).
    Formule : 10 * log10(lin)
    """
    return 10 * math.log10(lin)

# ---------- Calcul de la figure de bruit totale (Friis) ----------

def calc_nf(chain):
    """
    Calcule la NF totale (en dB) d'une chaîne donnée.
    Entrée : chain = liste d'étages, chaque élément doit contenir :
      - 'nf_lin'   : NF en linéaire (pas en dB)
      - 'gain_lin' : gain (linéaire, ratio de puissance)
    Algorithme : formule de Friis :
      NF_tot_lin = NF1 + (NF2 - 1)/G1 + (NF3 - 1)/(G1*G2) + ...
    Retour : NF totale en dB (utilise lin_to_db).
    Remarque : la 1ère NF doit être en linéaire et non nulle.
    """
    # NF linéaire du premier étage
    nf_tot = chain[0]['nf_lin']
    # produit cumulatif des gains (linéaire) des étages déjà rencontrés
    g_prod = chain[0]['gain_lin']
    # boucle sur les étages suivants
    for stage in chain[1:]:
        nf_tot += (stage['nf_lin'] - 1) / g_prod
        g_prod *= stage['gain_lin']
    return lin_to_db(nf_tot)

# ---------- Calcul de l'OP1dB total en sortie ----------

def calc_p1db(chain):
    """
    Calcule l'OP1dB de sortie d'une chaîne (en dBm).
    Méthode :
      - p1db_lin : OP1dB de chaque étage en mW (linéaire)
      - gain_after[i] : produit des gains linéaires des étages placés APRÈS l'étage i
      - contribution d'un étage i au P1dB total (en mW) est P1dB_i * gain_after[i]
      - on somme les inverses : 1 / P_total = sum_i 1/(P1dB_i * gain_after[i])
      - P_total (mW) = 1 / somme_inverse
      - retour en dBm via lin_to_db (car lin_to_db( mW ) -> dBm)
    Hypothèses / limites :
      - si un p1db_lin est nul ou manquant, cela lèvera une ZeroDivisionError.
      - s'assurer que gains et p1db sont en linéaire avant l'appel.
    """
    N = len(chain)
    gain_after = [1.0] * N  # gain total placé après chaque étage (linéaire)
    prod = 1.0
    # construire gain_after en sens inverse : gain_after[i] = produit(gain_k pour k>i)
    for idx in range(N-1, -1, -1):
        gain_after[idx] = prod
        prod *= chain[idx]['gain_lin']

    # somme des inverses pondérées
    inv_sum = sum(
        1 / (stage['p1db_lin'] * gain_after[i])
        for i, stage in enumerate(chain)
    )
    # résultat en mW -> lin_to_db retourne dBm
    return lin_to_db(1 / inv_sum)

# ---------- Construction de la chaîne RF depuis le YAML ----------

def build_chain(arch, use_gain_max=False):
    """
    Transforme la description YAML (valeurs en dB/dBm) en une liste d'étages avec valeurs linéaires.
    Paramètres :
      - arch : liste d'éléments YAML décrivant chaque composant
      - use_gain_max : si True, préfère 'gain_dB_max' si présent, sinon 'gain_dB'

    Comportements particuliers :
      - Pour les filtres et switches, on considère que la NF (en dB) = perte d'insertion (insertion_loss_dB).
        => gain_dB = - insertion_loss_dB  (car perte)
      - Si nf_dB absent pour un amplificateur, on prend nf_dB = |gain_dB| (approximation conservative)
      - Si op1db_dBm absent, valeur par défaut distante (ici 1000 dBm) -> attention overflow possible si converti en mW
        (la valeur 1000 sert d'indicateur "virtuel" d'absence de contrainte ; c'est une pratique risquée en calculs réels)
    Retour :
      liste de dicts : { 'name', 'type', 'gain_lin', 'nf_lin', 'p1db_lin' }
      - gain_lin : facteur (unitless)
      - nf_lin   : ratio linéaire (>1)
      - p1db_lin : puissance en mW (linéaire)
    """
    chain = []
    for c in arch:
        # si composant passif de filtrage => perte fournie
        if c['type'] in ['filter', 'switch']:
            loss = c['insertion_loss_dB']  # valeur positive (dB)
            gain_dB = -loss                 # gain = -perte
            nf_dB = loss                    # NF d'un passif = perte d'insertion
        else:
            # choisir gain nominal ou gain max selon le mode
            gain_dB = c.get('gain_dB_max', c['gain_dB']) if use_gain_max else c['gain_dB']
            # NF fourni ou estimation conservatrice (abs(gain_dB))
            nf_dB = c.get('nf_dB', abs(gain_dB))

        # OP1dB : si présent, valeur en dBm ; sinon 1000 (valeur par défaut)
        # NOTE : 1000 dBm -> db_to_lin(1000) fera 10**(100) -> très grand float
        p1dB = c.get('op1db_dBm', 1000)

        chain.append({
            'name': c['name'],
            'type': c['type'],
            'gain_lin': db_to_lin(gain_dB),
            'nf_lin': db_to_lin(nf_dB),
            'p1db_lin': db_to_lin(p1dB)
        })
    return chain

# ---------- Fonctions d'affichage console (colorées) ----------

def print_header(title):
    """
    Print d'un en-tête simple (fond noir + texte blanc).
    """
    print(Back.BLACK + Fore.WHITE + f"  {title}  " + Style.RESET_ALL)


def print_section(title, value, unit, color=Fore.WHITE):
    """
    Affiche une ligne de synthèse formatée.
    Exemple :
      ■■ Gain total   : 10.00 dB
    - title : texte court
    - value : valeur numérique
    - unit  : unité en texte (ex: "dB", "dBm")
    - color : couleur (optionnel)
    """
    bar = '■' * 3
    print(f"{color}{bar} {title:<15}: {value:>6.2f} {unit}{Style.RESET_ALL}")


def print_spacers():
    """
    Ligne de séparation visuelle.
    """
    print("_" * 60 + "\n")

# ---------- Main / point d'entrée ----------

def main():
    """
    Flux principal :
    - charge YAML param.yaml situé dans le même dossier que ce script
    - construit deux chaînes (mode min / mode max si gain_dB_max fourni)
    - calcule : NF total (min/max), OP1dB sortie (min/max), gains totaux (min/max), IP1dB entrée
    - affiche le tout
    """
    # chemin vers param.yaml dans le même dossier que ce script
    base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "param.yaml")
    yaml_filename = os.path.basename(path)
    print(f"Fichier YAML exécuté : {Fore.CYAN}{yaml_filename}{Style.RESET_ALL}")

    # chargement YAML
    with open(path, 'r') as f:
        data = yaml.safe_load(f)
    arch = data['architecture']

    # construire chaînes min / max
    ch_min = build_chain(arch, use_gain_max=False)
    ch_max = build_chain(arch, use_gain_max=True)

    # calculs principaux
    nf_min, nf_max = calc_nf(ch_min), calc_nf(ch_max)
    p1_min, p1_max = calc_p1db(ch_min), calc_p1db(ch_max)

    # gains totaux (dB) : produit des gains linéaires passé en dB
    g_min = lin_to_db(math.prod(s['gain_lin'] for s in ch_min))
    g_max = lin_to_db(math.prod(s['gain_lin'] for s in ch_max))

    # IP1dB entrée = OP1dB_sortie - Gain_total
    ip1_min, ip1_max = p1_min - g_min, p1_max - g_max

    # affichage chaîne (avec couleurs par type)
    line = " → ".join(f"{TYPE_COLORS.get(s['type'], '')}{s['name']}{Style.RESET_ALL}" for s in ch_min)

    print_spacers()
    print(f"{Back.BLACK+Fore.WHITE}{'■'*3} {'Chaîne RF':<8}:{Style.RESET_ALL} {line}\n")
    print_spacers()

    # résultats
    print(f"{Back.BLACK+Fore.WHITE} Résultats (min & max):{Style.RESET_ALL}\n")
    # Gains
    print_section("Gain total (min)   ", g_min, "dB")
    print_section("Gain total (max)  ", g_max, "dB")
    print()
    # NF
    print_section("NF total (min)     ", nf_min, "dB")
    print_section("NF total (max)     ", nf_max, "dB")
    print()
    # OP1dB sortie
    print_section("OP1dB sortie (min) ", p1_min, "dBm")
    print_section("OP1dB sortie (max) ", p1_max, "dBm")
    print()
    # IP1dB entrée
    print_section("IP1dB entrée (min) ", ip1_min, "dBm")
    print_section("IP1dB entrée (max) ", ip1_max, "dBm")
    print_spacers()

# Exécution quand lancé directement
if __name__ == "__main__":
    main()
