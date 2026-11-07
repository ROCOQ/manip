# CLAUDE.md

Kit pour utiliser un émulateur Wii U sur iPad. Langue du projet : **français**.

- `docs/` : guides (installation, dump des jeux, dépannage).
- `tools/check_wiiu_files.py` : vérification des fichiers de jeux, sans dépendances, Python 3.8+.
- `tests/` : `python3 -m unittest discover -s tests`, à lancer après chaque modification de `tools/`.
- `.claude/agents/` : agents wiiu-ipad-setup, wiiu-troubleshooter, wiiu-game-checker.

Règles : ne jamais ajouter de jeux, ROMs, clés, firmwares, ni de liens pour en télécharger.
Ne jamais committer de fichiers de jeux (voir .gitignore).
