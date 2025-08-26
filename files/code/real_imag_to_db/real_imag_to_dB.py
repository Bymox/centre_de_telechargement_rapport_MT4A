import numpy as np
import os

def convert_s2p_to_two_dat_files(s2p_path):
    freqs = []
    s11_db = []
    s21_db = []

    with open(s2p_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('#') or not line:
                continue  # Ignore commentaires et lignes vides

            parts = line.split()
            if len(parts) < 5:
                continue  # Faut au moins freq, S11, S21

            freq = float(parts[0])
            s11_real, s11_imag = float(parts[1]), float(parts[2])
            s21_real, s21_imag = float(parts[3]), float(parts[4])

            s11_mag = np.abs(complex(s11_real, s11_imag))
            s21_mag = np.abs(complex(s21_real, s21_imag))

            s11_db_val = 20 * np.log10(s11_mag) if s11_mag > 0 else -100
            s21_db_val = 20 * np.log10(s21_mag) if s21_mag > 0 else -100

            freqs.append(freq)
            s11_db.append(s11_db_val)
            s21_db.append(s21_db_val)

    # Préparation des noms de fichiers
    base_name = os.path.splitext(s2p_path)[0]
    s11_path = base_name + "_S11.dat"
    s21_path = base_name + "_S21.dat"

    # Écriture du fichier S11
    with open(s11_path, 'w') as f_s11:
        f_s11.write("# Frequency(Hz)\tS11(dB)\n")
        for f, s11 in zip(freqs, s11_db):
            f_s11.write(f"{f:.0f}\t{s11:.2f}\n")

    # Écriture du fichier S21
    with open(s21_path, 'w') as f_s21:
        f_s21.write("# Frequency(Hz)\tS21(dB)\n")
        for f, s21 in zip(freqs, s21_db):
            f_s21.write(f"{f:.0f}\t{s21:.2f}\n")

    print(f"✅ Fichiers créés :\n - {s11_path}\n - {s21_path}")

# Utilisation
s2p_file = "C:/Users/a942666/OneDrive - ATOS/Bureau/bank_18_24/LFCV-2302+_Plus25DegC.s2p"
convert_s2p_to_two_dat_files(s2p_file)
