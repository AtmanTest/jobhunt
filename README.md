# JobHunt Dashboard 🚀

Chasse d'emploi QA/SDET remote automatisée.

## Local (Flask — recommandé)
```bash
cd ~/Desktop/jobhunt
python3 app.py
```
→ http://localhost:5050

## GitHub Pages (statique)
1. Crée un repo GitHub
2. Copie les fichiers du dossier `docs/` à la racine (ou garde `/docs`)
3. Active GitHub Pages dans Settings → Pages → "Deploy from branch" → `/docs`
4. Ton site sera en ligne sur `https://tonpseudo.github.io/nom-du-repo/`

Pour mettre à jour les offres :
```bash
python3 scraper.py          # scrape les offres
python3 -c "from scraper import export_static_json; export_static_json()"  # exporte en JSON
git add -A && git commit -m "update jobs" && git push
```

## Cronjob quotidien
Un cronjob Hermes envoie les nouvelles offres sur WhatsApp tous les jours à 8h.
