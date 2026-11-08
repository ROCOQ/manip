#!/bin/zsh
# Installation sur Mac : environnement Python, dépendances, lancement automatique au démarrage.
set -euo pipefail
cd "$(dirname "$0")/.."
DIR="$(pwd)"

command -v python3 >/dev/null || { echo "Installez Python 3.10+ (https://www.python.org/downloads/ ou brew install python)"; exit 1; }
python3 -m venv .venv
.venv/bin/pip install --upgrade pip >/dev/null
.venv/bin/pip install -r requirements.txt

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "→ Ouvrez $DIR/.env et collez votre clé ANTHROPIC_API_KEY, puis relancez ce script."
  exit 0
fi
mkdir -p data
sed "s#CHEMIN_DU_DEPOT#$DIR#g" deploy/fr.voiture.agents.plist > ~/Library/LaunchAgents/fr.voiture.agents.plist
launchctl unload ~/Library/LaunchAgents/fr.voiture.agents.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/fr.voiture.agents.plist
sleep 3
echo "✓ Serveur lancé sur http://127.0.0.1:8000 (et relancé automatiquement à chaque démarrage)."
grep -h "mot de passe de l'app généré" data/serveur.log 2>/dev/null | tail -1 || true
echo "Pour l'iPhone : voir la section « Accès depuis l'iPhone » du README (Tailscale)."
