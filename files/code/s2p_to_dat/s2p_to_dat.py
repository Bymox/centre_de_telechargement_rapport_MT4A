import os  # Permet de manipuler fichiers et dossiers

# === FONCTION PRINCIPALE ===
def convert_s2p(s2p_path: str, output_dir: str):
    """
    Cette fonction prend un fichier .s2p et crée deux fichiers .dat :
      - <nom_du_fichier>_S11.dat : fréquence et S11
      - <nom_du_fichier>_S21.dat : fréquence et S21
    """
    
    # Vérifie que le fichier .s2p existe. Si pas trouvé, arrête le programme
    if not os.path.isfile(s2p_path):
        raise FileNotFoundError(f"Fichier introuvable : {s2p_path}")

    # Crée le dossier de sortie si il n'existe pas encore
    os.makedirs(output_dir, exist_ok=True)

    # Récupère le nom du fichier sans son chemin ni son extension
    base = os.path.splitext(os.path.basename(s2p_path))[0]

    # Crée les chemins des fichiers de sortie
    s11_out = os.path.join(output_dir, f"{base}_S11.dat")
    s21_out = os.path.join(output_dir, f"{base}_S21.dat")

    # Ouvre le fichier .s2p pour lecture et les fichiers de sortie pour écriture
    with open(s2p_path, "r") as fin, \
         open(s11_out, "w") as f11, \
         open(s21_out, "w") as f21:

        # Écrit les titres des colonnes dans les fichiers .dat
        f11.write("# freq(Hz)\tS11\n")
        f21.write("# freq(Hz)\tS21\n")

        # Parcourt chaque ligne du fichier .s2p
        for line in fin:
            line = line.strip()  # Supprime les espaces au début et à la fin

            # Ignore les lignes vides et les commentaires
            if not line or line.startswith("#") or line.startswith("!"):
                continue

            # Sépare la ligne en morceaux
            parts = line.split()

            # Si la ligne n'a pas assez de données, on l'ignore
            if len(parts) < 4:
                continue

            # On prend la fréquence, S11 et S21 (colonne 0,1,3)
            freq, s11, s21 = parts[0], parts[1], parts[3]

            # Écrit les données dans les fichiers de sortie
            f11.write(f"{freq}\t{s11}\n")
            f21.write(f"{freq}\t{s21}\n")

    # Affiche un message pour dire que la conversion est terminée
    print(f"✅ Fichier converti : {s2p_path}")
    print(f"   → S11 : {s11_out}")
    print(f"   → S21 : {s21_out}")


# === PARTIE EXECUTABLE SI ON LANCE LE SCRIPT ===
if __name__ == "__main__":
    # === MODIFIEZ CES CHEMINS POUR VOTRE CAS ===
    input_file  = r"C:\Users\a942666\OneDrive - ATOS\Bureau\HPF_4GHz\HPF4G.s2p"  # Fichier .s2p à convertir
    output_dir  = r"C:\Users\a942666\OneDrive - ATOS\Bureau\S21_HPF.dat"          # Dossier où mettre les .dat

    # Appelle la fonction principale pour faire la conversion
    convert_s2p(input_file, output_dir)
