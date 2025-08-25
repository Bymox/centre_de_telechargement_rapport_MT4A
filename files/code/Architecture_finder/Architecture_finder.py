#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script : architecture_optimizer.py
But    : générer et scorer des architectures RF (placement LNAs + configurations d'atténuateurs)
Auteur : (ton nom)
Usage  : placer le YAML d'entrée (components.yaml) dans le même dossier et lancer le script.
Sortie : results.txt (liste des architectures testées) + résumé console (meilleure architecture)

Conventions et unités :
 - Tous les niveaux en dB (gain_dB, insertion_loss_dB, nf_dB)
 - OP1dB dans le YAML donné en dBm (op1db_dBm ou p1db_dBm accepted)
 - Fonctions utilitaires convertissent dB <-> linéaire :
     lin = 10^(dB/10)
 - Pour les composants passifs (type 'filter' ou 'switch'), on attend
   insertion_loss_dB (positive) et on considère :
     gain_dB = -insertion_loss_dB
     nf_dB   = insertion_loss_dB  (hypothèse : NF = pertes d'insertion)
 - Si un champ manque, valeurs par défaut raisonnables sont appliquées
   (ex : p1db par défaut = +1000 dBm -> non contraignant).
"""

import yaml
import itertools
import math
import os

# -------------------------
# Utils de base (conversions)
# -------------------------
def non_empty_subsets(lst):
    """
    Retourne toutes les sous-ensembles non vides de la liste `lst`.
    Utilisé pour tester toutes les combinaisons possibles de LNAs mobiles.
    """
    return [list(subset) for r in range(1, len(lst)+1) for subset in itertools.combinations(lst, r)]

def db_to_lin(db):
    """Convertit dB -> linéaire (puissance facteur)."""
    return 10 ** (db / 10)

def lin_to_db(lin):
    """Convertit linéaire -> dB. ATTENTION: lin doit être > 0."""
    return 10 * math.log10(lin)

# -------------------------
# Chargement YAML
# -------------------------
def load_config(yaml_filename):
    """
    Charge un fichier YAML situé dans le même dossier que ce script.
    Retourne le contenu Python (dictionnaires / listes).
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    yaml_path = os.path.join(script_dir, yaml_filename)
    with open(yaml_path, 'r') as f:
        return yaml.safe_load(f)

# -------------------------
# Calculs physiques
# -------------------------
def calc_nf(chain):
    """
    Calcule le NF total de la chaîne via la formule de Friis (en linéaire),
    puis convertit en dB pour retour.
    chain: liste d'étages avec 'gain_lin' et 'nf_lin' (valeurs linéaires).
    NF_total_lin = NF1 + (NF2-1)/G1 + (NF3-1)/(G1*G2) + ...
    Retour: NF total en dB.
    """
    nf_total_lin = chain[0]['nf_lin']
    gain_prod = chain[0]['gain_lin']
    for stage in chain[1:]:
        nf_total_lin += (stage['nf_lin'] - 1) / gain_prod
        gain_prod *= stage['gain_lin']
    return lin_to_db(nf_total_lin)

def calc_p1db(chain):
    """
    Calcule l'OP1dB total en sortie d'une chaîne.
    Méthode utilisée (identique au second script de référence) :
      - pour chaque étage i, on calcule le gain restant après l'étage: gain_after[i]
        (produit des gains des étages qui suivent)
      - on somme les inverses pondérées : inv_sum = sum( 1 / (p1db_lin_i * gain_after[i]) )
      - P1dB_total_lin = 1 / inv_sum
      - on retourne P1dB en dB (dBm, car p1db_lin provient d'une conversion depuis dBm)
    Remarques :
      - Si un étage n'a pas de p1db défini ou valeur non positive, on l'ignore (contrib. nulle).
      - Si inv_sum == 0 (cas pathologique), on retourne -inf pour signaler l'impossibilité.
    """
    if not chain:
        return float('-inf')

    N = len(chain)
    gain_after = [1.0] * N
    prod = 1.0
    # calcule produit des gains après chaque étage (on parcourt à l'envers)
    for idx in range(N-1, -1, -1):
        gain_after[idx] = prod
        prod *= chain[idx]['gain_lin']

    inv_sum = 0.0
    for i, stage in enumerate(chain):
        p1_lin = stage.get('p1db_lin', None)
        if not p1_lin or p1_lin <= 0:
            # pas de P1dB renseigné => on l'ignore (comportement non contraignant)
            continue
        inv_sum += 1.0 / (p1_lin * gain_after[i])

    if inv_sum <= 0:
        return float('-inf')

    p1_total_lin = 1.0 / inv_sum
    return lin_to_db(p1_total_lin)

# -------------------------
# Gestion des blocs verrouillés
# -------------------------
def group_locked_stages(stages):
    """
    Construit des 'blocs' à partir d'une liste de composants fixes en respectant
    le champ `locked_with_next`: si un composant a locked_with_next=True,
    on le regroupe avec le suivant dans le même bloc.
    Retour: liste de blocs (chacun une liste de composants).
    """
    blocks = []
    current_block = []
    for comp in stages:
        current_block.append(comp)
        if not comp.get('locked_with_next', False):
            blocks.append(current_block)
            current_block = []
    if current_block:
        blocks.append(current_block)
    return blocks

def flatten_block_names(block):
    """Retourne un nom simple pour le bloc : concaténation des noms séparés par ' + '."""
    return " + ".join(comp['name'] for comp in block)

def flatten_block_stages(block):
    """
    Transforme un bloc (liste de composants) en un seul 'stage' synthétique.
    Important : on calcule le NF et l'OP1dB du bloc **en appliquant exactement**
    les mêmes formules de cascade (calc_nf et calc_p1db) à la sous-chaîne interne.
    Cela évite les approximations (somme naïve des NF qui faussent les résultats).

    Retourne un dict avec:
      - name, gain_dB (somme), gain_dB_max (somme), nf_dB (calc Friis sur sous-chaîne),
        p1db_dBm (OP1dB du bloc), gain_lin, nf_lin, p1db_lin, type='block'
    """
    subchain = []
    total_gain_dB = 0.0
    total_gain_dB_max = 0.0

    for comp in block:
        # Pour les passifs (filter, switch) : on cherche insertion_loss_dB (positive)
        # gain_comp_dB = - insertion_loss_dB ; nf_comp_dB = insertion_loss_dB
        if comp.get('type') in ['filter', 'switch'] and 'insertion_loss_dB' in comp:
            loss = float(comp['insertion_loss_dB'])
            gain_comp_dB = -abs(loss)
            nf_comp_dB = abs(loss)
        else:
            gain_comp_dB = float(comp.get('gain_dB', 0.0))
            nf_comp_dB = float(comp.get('nf_dB', abs(gain_comp_dB)))

        # p1db en dBm : accepte p1db_dBm ou op1db_dBm ; défaut = +1000 dBm (non contraignant)
        p1db_val = comp.get('p1db_dBm', comp.get('op1db_dBm', 1000.0))

        # Construire l'entrée en linéaire attendue par calc_nf / calc_p1db
        substage = {
            'name': comp.get('name', ''),
            'type': comp.get('type', ''),
            'gain_lin': db_to_lin(gain_comp_dB),
            'nf_lin': db_to_lin(nf_comp_dB),
            'p1db_lin': db_to_lin(float(p1db_val))
        }
        subchain.append(substage)

        total_gain_dB += gain_comp_dB
        total_gain_dB_max += float(comp.get('gain_dB_max', gain_comp_dB))

    # Calculs corrects par cascade sur la sous-chaîne
    block_nf_dB = calc_nf(subchain)        # NF du bloc en dB (Friis)
    block_p1db_dBm = calc_p1db(subchain)   # OP1dB du bloc en dBm

    return {
        'name': flatten_block_names(block),
        'gain_dB': total_gain_dB,
        'gain_dB_max': total_gain_dB_max,
        'nf_dB': block_nf_dB,
        'p1db_dBm': block_p1db_dBm,
        'gain_lin': db_to_lin(total_gain_dB),
        'nf_lin': db_to_lin(block_nf_dB),
        'p1db_lin': db_to_lin(block_p1db_dBm),
        'type': 'block'
    }

# -------------------------
# Génération de toutes les architectures
# -------------------------
def generate_all_chains(blocks, movable_lnas, attenuators):
    """
    Insère les LNAs mobiles dans les positions possibles entre les blocs fixes,
    puis insère les atténuateurs (avec toutes les combinaisons de réglages possibles).
    Retourne une liste d'architectures testées avec métriques de base.
    """
    insert_positions = list(range(1, len(blocks)))  # positions entre blocs
    all_architectures = []

    # itère sur choix de positions pour les LNAs mobiles
    for lna_positions in itertools.combinations(insert_positions, len(movable_lnas)):
        for lna_perm in itertools.permutations(movable_lnas):
            temp_blocks = blocks.copy()
            # insère les LNAs (on garde l'ordre des positions)
            for pos, lna in sorted(zip(lna_positions, lna_perm), reverse=True):
                temp_blocks.insert(pos, lna.copy())

            # préparer toutes les configurations d'atténuateurs (options)
            att_configs_per_att = []
            for att in attenuators:
                att_configs = []
                if 'gain_dB_options' in att:
                    for att_gain_dB in att['gain_dB_options']:
                        att_copy = att.copy()
                        att_copy['gain_dB'] = att_gain_dB
                        att_copy['gain_lin'] = db_to_lin(att_gain_dB)
                        att_copy['nf_lin'] = db_to_lin(abs(att_gain_dB))
                        att_copy['p1db_lin'] = db_to_lin(att_copy.get('p1db_dBm', att_copy.get('op1db_dBm', 1000)))
                        att_configs.append(att_copy)
                else:
                    att_copy = att.copy()
                    att_copy['gain_lin'] = db_to_lin(att['gain_dB'])
                    att_copy['nf_lin'] = db_to_lin(abs(att['gain_dB']))
                    att_copy['p1db_lin'] = db_to_lin(att_copy.get('p1db_dBm', att_copy.get('op1db_dBm', 1000)))
                    att_configs.append(att_copy)
                att_configs_per_att.append(att_configs)

            # positions possibles pour insérer les atténuateurs
            att_positions = list(range(1, len(temp_blocks)))
            for att_pos_combo in itertools.combinations(att_positions, len(attenuators)):
                for att_gain_combo in itertools.product(*att_configs_per_att):
                    full_chain = temp_blocks.copy()
                    # insère les atténuateurs (en partant de la fin pour respecter positions)
                    for pos, att in sorted(zip(att_pos_combo, att_gain_combo), reverse=True):
                        full_chain.insert(pos, att)

                    # garantir que les champs linéaires sont présents pour chaque stage
                    for s in full_chain:
                        if 'gain_lin' not in s:
                            s['gain_lin'] = db_to_lin(s.get('gain_dB', 0.0))
                        if 'nf_lin' not in s:
                            s['nf_lin'] = db_to_lin(s.get('nf_dB', abs(s.get('gain_dB', 0.0))))
                        if 'p1db_lin' not in s:
                            p1db_val = s.get('p1db_dBm', s.get('op1db_dBm', 1000.0))
                            s['p1db_lin'] = db_to_lin(p1db_val)

                    gain_lin = math.prod(stage['gain_lin'] for stage in full_chain)
                    gain_dB = lin_to_db(gain_lin)
                    nf = calc_nf(full_chain)      # NF total en dB (Friis)
                    p1db = calc_p1db(full_chain)  # OP1dB sortie en dBm

                    all_architectures.append({
                        'chain': [s['name'] for s in full_chain],
                        'nf_dB': nf,
                        'p1db_dBm': p1db,   # OP1dB (sortie)
                        'gain_dB': gain_dB,
                        'full_chain': full_chain
                    })
    return all_architectures

# -------------------------
# Calcul min/max (atténuateurs)
# -------------------------
def compute_metrics_gain_min_max(full_chain, attenuators):
    """
    Construit deux variantes de la chaîne :
      - chain_min : atténuateurs à leur valeur minimale (min gain_dB)
      - chain_max : atténuateurs à leur valeur maximale (max gain_dB)
    Puis calcule pour chaque variante :
      - gain total (dB)
      - NF total (dB)
      - OP1dB sortie (dBm)
    Enfin calcule IP1dB d'entrée :
      IP1dB = OP1dB_sortie - Gain_total  (valeurs min/max correspondantes)
    Retour: gain_min_dB, gain_max_dB, nf_min, nf_max, p1db_min, p1db_max, ip1_min, ip1_max
    """
    chain_max = []
    chain_min = []

    for stage in full_chain:
        # traiter à la fois 'atten' et 'attenuator'
        if stage['type'] in ['attenuator', 'atten']:
            s = stage.copy()
            if 'gain_dB_options' in s:
                max_gain = max(s['gain_dB_options'])
                min_gain = min(s['gain_dB_options'])
            else:
                max_gain = min_gain = s['gain_dB']
            s_max = s.copy()
            s_max['gain_dB'] = max_gain
            s_max['gain_lin'] = db_to_lin(max_gain)
            s_max['nf_lin'] = db_to_lin(abs(max_gain))

            s_min = s.copy()
            s_min['gain_dB'] = min_gain
            s_min['gain_lin'] = db_to_lin(min_gain)
            s_min['nf_lin'] = db_to_lin(abs(min_gain))

            chain_max.append(s_max)
            chain_min.append(s_min)
        else:
            chain_max.append(stage)
            chain_min.append(stage)

    gain_max_lin = math.prod(s['gain_lin'] for s in chain_max)
    gain_max_dB = lin_to_db(gain_max_lin)
    nf_max = calc_nf(chain_max)
    p1db_max = calc_p1db(chain_max)

    gain_min_lin = math.prod(s['gain_lin'] for s in chain_min)
    gain_min_dB = lin_to_db(gain_min_lin)
    nf_min = calc_nf(chain_min)
    p1db_min = calc_p1db(chain_min)

    # IP1dB (entrée) : OP1dB_sortie - gain_total (valeurs cohérentes min/max)
    ip1_min = p1db_min - gain_min_dB
    ip1_max = p1db_max - gain_max_dB

    return gain_min_dB, gain_max_dB, nf_min, nf_max, p1db_min, p1db_max, ip1_min, ip1_max

# -------------------------
# Scoring
# -------------------------
def score_architecture_metrics(metrics, target_gain, nf_max_target, p1db_min_target):
    """
    Score = somme des erreurs quadratiques pondérées par les cibles :
      - erreur sur gain min et max par rapport à target_gain
      - pénalité si NF_max (cas pessimiste) dépasse nf_max_target
      - pénalité si OP1dB_min (cas pessimiste) est < p1db_min_target
    NOTE : les IP1dB ne sont pas utilisés dans le score actuel.
    """
    gain_min, gain_max, nf_min, nf_max, p1db_min, p1db_max, ip1_min, ip1_max = metrics
    err_gain_min = (gain_min - target_gain) ** 2
    err_gain_max = (gain_max - target_gain) ** 2
    err_nf = max(0, nf_max - nf_max_target) ** 2
    err_p1db = max(0, p1db_min_target - p1db_min) ** 2
    return err_gain_min + err_gain_max + err_nf + err_p1db

# -------------------------
# Main
# -------------------------
def main():
    # charge le YAML (attendu: 'components.yaml' à côté du script)
    config = load_config('components.yaml')
    target_gain = config['gain_total_target_dB']
    nf_max_target = config['nf_max_dB']
    p1db_min_target = config['p1db_min_dBm']
    components = config['components']

    # séparation composants en listes : fixed (blocs immuables), lnas (mobiles), attenuators
    fixed = []
    lnas = []
    attenuators = []

    for comp in components:
        comp = comp.copy()

        # p1db peut être dans p1db_dBm ou op1db_dBm selon ton YAML -> unifier
        p1db_val = comp.get('p1db_dBm', comp.get('op1db_dBm', None))
        if p1db_val is None:
            p1db_val = 1000.0  # valeur non contraignante si absent
        comp['p1db_lin'] = db_to_lin(p1db_val)

        # traitement des atténuateurs (options ou valeur fixe)
        if comp['type'] in ['attenuator', 'atten']:
            gain_ref = comp['gain_dB_options'][0] if 'gain_dB_options' in comp else comp['gain_dB']
            comp['gain_lin'] = db_to_lin(gain_ref)
            comp['nf_lin'] = db_to_lin(abs(gain_ref))
        else:
            # si filtre/switch : convertit insertion_loss_dB -> gain_dB négatif et nf
            if comp.get('type') in ['filter', 'switch'] and 'insertion_loss_dB' in comp:
                loss = comp['insertion_loss_dB']
                comp['gain_dB'] = -abs(loss)
                comp['nf_dB'] = loss
            comp['gain_lin'] = db_to_lin(comp.get('gain_dB', 0.0))
            comp['nf_lin'] = db_to_lin(comp.get('nf_dB', 30.0))

        # classification
        if comp['type'] == 'lna' and not comp.get('fixed', False):
            lnas.append(comp)
        elif comp['type'] in ['attenuator', 'atten']:
            if comp.get('fixed', False):
                fixed.append(comp)
            else:
                attenuators.append(comp)
        else:
            fixed.append(comp)

    # grouper les composants fixes en blocs respectant locked_with_next
    blocks = group_locked_stages(fixed)
    block_stages = [flatten_block_stages(b) for b in blocks]

    # générer toutes les architectures en insérant sous-ensembles de LNAs mobiles
    all_archs = []
    for lna_subset in non_empty_subsets(lnas):
        archs = generate_all_chains(block_stages, lna_subset, attenuators)
        all_archs.extend(archs)

    if not all_archs:
        print("❌ Aucune architecture générée.")
        return

    # scorer chaque architecture et écrire résultats
    scored_archs = []
    for arch in all_archs:
        metrics = compute_metrics_gain_min_max(arch['full_chain'], attenuators)
        score = score_architecture_metrics(metrics, target_gain, nf_max_target, p1db_min_target)
        scored_archs.append({
            'chain': arch['chain'],
            'metrics': metrics,
            'score': score
        })

    # tri et sauvegarde
    scored_archs_sorted = sorted(scored_archs, key=lambda a: a['score'])
    script_dir = os.path.dirname(os.path.abspath(__file__))
    results_path = os.path.join(script_dir, "results.txt")
    with open(results_path, "w", encoding="utf-8") as f:
        f.write("=== 🧪 Toutes les architectures testées : {} ===\n\n".format(len(scored_archs_sorted)))
        for arch in scored_archs_sorted:
            gain_min_dB, gain_max_dB, nf_min, nf_max, p1db_min, p1db_max, ip1_min, ip1_max = arch['metrics']
            f.write(f"Chaîne: {arch['chain']}\n")
            f.write(f"  -> Gain min = {gain_min_dB:.2f} dB | Gain max = {gain_max_dB:.2f} dB\n")
            f.write(f"     NF min   = {nf_min:.2f} dB    | NF max   = {nf_max:.2f} dB\n")
            f.write(f"     OP1dB sort. min = {p1db_min:.2f} dBm | OP1dB sort. max = {p1db_max:.2f} dBm\n")
            f.write(f"     IP1dB entr. min = {ip1_min:.2f} dBm | IP1dB entr. max = {ip1_max:.2f} dBm\n")
            f.write(f"     Score    = {arch['score']:.4f}\n\n")

    # afficher meilleure architecture
    best_arch = scored_archs_sorted[0]
    gain_min_dB, gain_max_dB, nf_min, nf_max, p1db_min, p1db_max, ip1_min, ip1_max = best_arch['metrics']

    print("\n=== ✅ Meilleure architecture trouvée ===")
    print(f"Chaîne: {best_arch['chain']}\n")
    print(f"Gain min (atténuateurs à min) : {gain_min_dB:.2f} dB")
    print(f"Gain max (atténuateurs à max) : {gain_max_dB:.2f} dB\n")
    print(f"NF min (gain min)              : {nf_min:.2f} dB")
    print(f"NF max (gain max)              : {nf_max:.2f} dB\n")
    print(f"OP1dB sortie (min)             : {p1db_min:.2f} dBm")
    print(f"OP1dB sortie (max)             : {p1db_max:.2f} dBm\n")
    print(f"IP1dB entrée (min)             : {ip1_min:.2f} dBm")
    print(f"IP1dB entrée (max)             : {ip1_max:.2f} dBm\n")
    print(f"Score                          : {best_arch['score']:.4f}\n")

if __name__ == "__main__":
    main()
