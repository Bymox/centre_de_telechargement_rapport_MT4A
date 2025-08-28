#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diff_lignes.py – compare Fichier1.txt et Fichier2.txt ligne par ligne.

Affiche au terminal :
Ligne 7 :
    Fichier1.txt | <contenu ligne 7 fichier 1>
    Fichier2.txt | <contenu ligne 7 fichier 2>
"""

import os
import itertools

# -------------------------------------------------------------------------
# Chemins des fichiers (même dossier que ce script)
# -------------------------------------------------------------------------
script_dir = os.path.dirname(os.path.abspath(__file__))

file1_path = os.path.join(script_dir, "Fichier1.txt")
file2_path = os.path.join(script_dir, "Fichier2.txt")

# Vérifications basiques
for path in (file1_path, file2_path):
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Introuvable : {path}")

# -------------------------------------------------------------------------
# Lecture des fichiers
# -------------------------------------------------------------------------
with open(file1_path, encoding="utf-8") as f1, open(file2_path, encoding="utf-8") as f2:
    lines1 = [line.rstrip("\n") for line in f1]
    lines2 = [line.rstrip("\n") for line in f2]

# -------------------------------------------------------------------------
# Comparaison ligne par ligne
# -------------------------------------------------------------------------
max_len = max(len(lines1), len(lines2))
differences = 0

for idx in range(max_len):
    # Récupère la ligne ou '<-absente->' si hors index
    l1 = lines1[idx] if idx < len(lines1) else "<-- ligne absente -->"
    l2 = lines2[idx] if idx < len(lines2) else "<-- ligne absente -->"

    if l1 != l2:
        differences += 1
        print(f"\nLigne {idx + 1} :")
        print(f"  Fichier1.txt | {l1}")
        print(f"  Fichier2.txt | {l2}")

if differences == 0:
    print("✅ Aucun écart : les deux fichiers sont identiques.")
else:
    print(f"\nNombre total de lignes différentes : {differences}")
