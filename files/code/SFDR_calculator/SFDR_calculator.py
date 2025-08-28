import yaml
import math

# -----------------------------------------------------------
# Calcule la puissance de bruit intégrée dans une bande donnée
# -----------------------------------------------------------
def noise_power_dBm(bw_hz: float, nf_db: float) -> float:
    """
    Puissance de bruit thermique intégrée dans la bande,
    exprimée en dBm.
    Formule : -174 dBm/Hz + 10*log10(BW) + NF
    """
    return -174 + 10 * math.log10(bw_hz) + nf_db


# -----------------------------------------------------------
# Estimation de l’IIP3 à partir du point de compression 1 dB
# -----------------------------------------------------------
def estimate_iip3_dbm(ip1db_dbm: float, delta_db: float = 10.0) -> float:
    """
    Approximation empirique :
    IIP3 ≈ IP1dB + Δ (par défaut Δ = 10 dB)
    """
    return ip1db_dbm + delta_db


# -----------------------------------------------------------
# Calcule le SFDR à partir de IP1dB, NF et bande passante
# -----------------------------------------------------------
def calculate_sfdr(ip1db_dbm: float, nf_db: float, bw_hz: float,
                   delta_db: float = 10.0) -> float:
    """
    SFDR (Spurious-Free Dynamic Range), exprimé en dB.
    Formule utilisée :
        SFDR = (2/3) * (IIP3 - N)
    où :
        - IIP3 est estimé à partir de IP1dB
        - N est la puissance de bruit dans la bande
    """
    iip3 = estimate_iip3_dbm(ip1db_dbm, delta_db)
    noise = noise_power_dBm(bw_hz, nf_db)
    return (2.0 / 3.0) * (iip3 - noise)


# -----------------------------------------------------------
# Fonction principale : lecture des paramètres et affichage
# -----------------------------------------------------------
def main():
    # Ouverture du fichier YAML contenant les paramètres
    with open("params.yaml", "r") as f:
        data = yaml.safe_load(f)

    # Bande passante extraite du fichier
    bw = data["bandwidth_hz"]
    print(f"Bande passante : {bw/1e6:.1f} MHz\n")

    # En-tête du tableau affiché
    print(f"{'Freq (GHz)':>8} {'SFDR min (dB)':>14} {'SFDR max (dB)':>14}")

    # Parcours de chaque fréquence définie dans le YAML
    for f in data["frequencies"]:
        freq      = f["freq_ghz"]
        nf_min    = f["nf_gain_min"]   # ← ATTENTION : vérifier que ce champ est bien une NF
        nf_max    = f["nf_gain_max"]
        ip1_min   = f["ip1db_min"]
        ip1_max   = f["ip1db_max"]

        # Calcul SFDR avec les valeurs min et max
        sfdr_min  = calculate_sfdr(ip1_min, nf_min, bw)
        sfdr_max  = calculate_sfdr(ip1_max, nf_max, bw)

        # Affichage formaté
        print(f"{freq:8.2f} {sfdr_min:14.2f} {sfdr_max:14.2f}")


# -----------------------------------------------------------
# Point d’entrée du script
# -----------------------------------------------------------
if __name__ == "__main__":
    main()
