#!/usr/bin/env python3
"""
Sélection du meilleur filtre (HPF/LPF) pour une RF donnée
— sans préselector banks.
"""

import os
import yaml
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import interp1d

print(">>> SCRIPT LANCÉ <<<")

# ---------------- utilitaires S21 ----------------
def load_s21_file(filepath):
    """Lit un fichier S21 simple (deux colonnes : freq [Hz], gain [dB]).
       Retourne dict avec grilles et une fonction d'interp (extrapolation = -100 dB)."""
    data = np.loadtxt(filepath)
    return {
        'freqs': data[:, 0],
        'gains': data[:, 1],
        'fun': interp1d(data[:, 0], data[:, 1], kind='cubic',
                        bounds_error=False, fill_value=-100.0)
    }

def load_all_filters(dirs, n_states):
    """Parcourt une liste de dossiers (ex: dataLPF1, dataHPF2...) et charge les fichiers
       nommés S21_state{st}.dat pour st in [0..n_states-1].
       Retourne un dict name -> filter_dict (comme load_s21_file)."""
    res = {}
    for d in dirs:
        for st in range(n_states):
            path = os.path.join(d, f"S21_state{st}.dat")
            if os.path.exists(path):
                key = f"{d}_state{st}"
                try:
                    res[key] = load_s21_file(path)
                except Exception as e:
                    print(f"⚠️ Erreur lecture {path} : {e} — on ignore ce fichier.")
    return res

def max_gain_brut(freqs, gains, target, tol):
    """Renvoie le gain max dans la fenêtre [target-tol, target+tol] sur arrays fournis.
       Si aucune donnée dans la fenêtre, renvoie -100 dB (valeur low)."""
    idx = np.where(np.abs(freqs - target) <= tol)[0]
    return np.max(gains[idx]) if idx.size else -100.0

def find_best_filter(filters, rf, imgf, tol, w0, wi):
    """Parcourt tous les filtres fournis dans `filters` et calcule un score:
       score = w0 * gain_at_rf - wi * gain_at_img. Retourne la meilleure config
       (name, filter_dict, gain_at_rf, gain_at_img, score) ou None si vide."""
    best_score = -np.inf
    best_cfg = None
    for name, f in filters.items():
        g_rf = max_gain_brut(f['freqs'], f['gains'], rf, tol)
        g_img = max_gain_brut(f['freqs'], f['gains'], imgf, tol)
        score = w0 * g_rf - wi * g_img
        if score > best_score:
            best_score = score
            best_cfg = (name, f, g_rf, g_img, score)
    return best_cfg

# ------------------ main -----------------------
def main(yaml_path):
    cfg = yaml.safe_load(open(yaml_path))

    # config
    mode = cfg.get('mode', 'supradyne')  # 'supradyne' ou 'infradyne'
    tol_hz = float(cfg.get('tolerance_hz', 30e6))
    w_center = float(cfg.get('weight_center', 10))
    w_image = float(cfg.get('weight_image', 10))
    n_states = int(cfg.get('n_states', 16))

    # dossiers des filtres (LPF + HPF). On va charger tout et considérer tous les filtres.
    lpf_dirs = cfg.get('lpf_dirs', [])
    hpf_dirs = cfg.get('hpf_dirs', [])

    # option: override de l'offset image si on veut contrôler précisément
    image_offset = cfg.get('image_offset_hz', None)
    if image_offset is not None:
        image_offset = float(image_offset)  # valeur signée à ajouter : imgf = rf + image_offset
    else:
        # valeurs par défaut (comportement historique dans ton code)
        if mode == 'supradyne':
            image_offset = +8e9
        else:
            image_offset = -6e9

    # charger tous les filtres
    print("Chargement LPF...")
    lpfs = load_all_filters(lpf_dirs, n_states)
    print(f"  -> {len(lpfs)} LPF chargés.")
    print("Chargement HPF...")
    hpfs = load_all_filters(hpf_dirs, n_states)
    print(f"  -> {len(hpfs)} HPF chargés.")

    # fusionner tous les filtres dans une seule famille
    all_filters = {}
    all_filters.update(lpfs)
    all_filters.update(hpfs)

    if not all_filters:
        print("❌ Aucun filtre chargé. Vérifie les chemins dans config.yaml.")
        return

    plt.ion()  # mode interactif
    for t in cfg.get('targets', []):
        rf = float(t['center_freq'])
        imgf = rf + image_offset  # calcul simple : offset configuré ou valeur par défaut

        print(f"\n🎯 RF = {rf/1e9:.3f} GHz")
        print(f"   Mode = {mode}, image_offset = {image_offset/1e9:.3f} GHz")
        print(f"   => Image freq = {imgf/1e9:.3f} GHz, tol ±{tol_hz/1e6:.1f} MHz")

        # trouver le meilleur filtre parmi tous
        best = find_best_filter(all_filters, rf, imgf, tol_hz, w_center, w_image)
        if best is None:
            print("❌ Aucun filtre trouvé.")
            continue

        name, f, g_rf, g_img, score = best
        print(f"✅ Filtre choisi : {name}")
        print(f"   • Gain @ RF   = {g_rf:.2f} dB")
        print(f"   • Gain @ Img  = {g_img:.2f} dB")
        print(f"   • Score       = {score:.2f}")
        sfdr_img = g_rf - g_img
        print(f"   • SFDR_image  = {sfdr_img:.3f} dB")

        # Préparation du plot (trace uniquement le filtre choisi)
        fmin = f['freqs'][0]
        fmax = f['freqs'][-1]
        freqs = np.linspace(fmin, fmax, 2000)
        resp = f['fun'](freqs)

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(freqs/1e9, resp, label=f"{name}", linewidth=2)

        # annotations : lignes verticales RF et Img
        ax.axvline(rf/1e9, color='red', linestyle='--', label=f"RF = {rf/1e9:.3f} GHz")
        ax.axvline(imgf/1e9, color='gray', linestyle=':', label=f"Image = {imgf/1e9:.3f} GHz")

        # annotation texte : gains
        ax.text(0.02, 0.95, f"Gain @ RF = {g_rf:.1f} dB\nGain @ Img = {g_img:.1f} dB",
                transform=ax.transAxes, fontsize=11, verticalalignment='top',
                bbox=dict(boxstyle="round", fc="w", alpha=0.85))

        ax.set_xlim(fmin/1e9, fmax/1e9)
        # y-limits choisies dynamiquement : [min-5, max+2] pour garder du contexte.
        ymin = np.nanmin(resp) if resp.size else -150
        ymax = np.nanmax(resp) if resp.size else 0
        ax.set_ylim(ymin - 5, max(0, ymax + 2))

        ax.set_title(f"Meilleur filtre pour RF={rf/1e9:.3f} GHz -> {name}")
        ax.set_xlabel("Fréquence (GHz)")
        ax.set_ylabel("Gain (dB)")
        ax.grid(True)
        ax.legend(loc='lower left')
        fig.tight_layout()
        plt.show(block=False)

    input("Appuie sur Entrée pour fermer les graphes...")

if __name__ == "__main__":
    main("config.yaml")
