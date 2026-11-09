# CLAUDE.md

Kit pour jouer sur iPad : émulation Wii U, et bibliothèque Steam en cloud gratuit (sans PC). Langue du projet : **français**.

- `docs/` : guides Wii U (installation, dump des jeux, dépannage) ; `docs/steam/` : Steam sur iPad (STEAM_IPAD.md, FLUIDITE.md).
- `tools/check_wiiu_files.py` : vérification des fichiers de jeux Wii U ; `tools/steam_cloud_check.py` : bibliothèque Steam vs catalogue GeForce NOW. Sans dépendances, Python 3.8+.
- `tests/` : `python3 -m unittest discover -s tests`, à lancer après chaque modification de `tools/`.
- `.claude/agents/` : agents wiiu-ipad-setup, wiiu-troubleshooter, wiiu-game-checker, steam-ipad-advisor, steam-library-checker, steam-cloud-troubleshooter.

Règles : ne jamais ajouter de jeux, ROMs, clés, firmwares, ni de liens pour en télécharger.
Ne jamais committer de fichiers de jeux (voir .gitignore), ni de clé API Steam ou d'identifiants.
Jamais de cracks, comptes partagés ni contournement des conditions d'utilisation des services cloud.
