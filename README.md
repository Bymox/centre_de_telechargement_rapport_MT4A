https://bymox.github.io/centre_de_telechargement_rapport_MT4A/
# Web Downloads Starter

Dépose tes ZIPs dans `files/` et ajoute une entrée dans `downloads.json`.
Héberge ce dossier tel quel (GitHub Pages, Netlify, S3, serveur nginx, etc.).

## Structure
- `index.html` — page de téléchargement qui lit `downloads.json` et affiche la liste.
- `assets/style.css` — styles minimalistes.
- `assets/main.js` — rendu de la liste + recherche.
- `downloads.json` — métadonnées pour chaque fichier (nom, version, taille, hash…).
- `files/` — tous les fichiers téléchargeables (exemples inclus).

## Ajouter un fichier
1. Copie ton `mon_fichier.zip` dans `files/`.
2. Ajoute une entrée dans `downloads.json`, exemple :
```json
{
  "filename": "mon_fichier.zip",
  "title": "Mon Bundle",
  "version": "v2.3",
  "size_bytes": 123456,
  "sha256": "…",
  "date": "2025-08-25",
  "description": "Ce que contient l'archive."
}
```
3. Recharge la page. Le bouton **Download** forcera le téléchargement.

## Vérifier le hash (optionnel)
- Windows: `CertUtil -hashfile files\mon_fichier.zip SHA256`
- macOS/Linux: `shasum -a 256 files/mon_fichier.zip`

## Note
Pas de backend : la liste ne peut pas s'auto-générer. On passe par `downloads.json` (simple et fiable).
