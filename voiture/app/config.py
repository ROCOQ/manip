"""Configuration lue dans les variables d'environnement (voir .env.example)."""
from __future__ import annotations

import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("VOITURE_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
DB_PATH = DATA_DIR / "voiture.sqlite3"

# Modèles Claude : le chef et les agents peuvent être réglés séparément.
CHEF_MODEL = os.environ.get("VOITURE_CHEF_MODEL", "claude-opus-5-5")
AGENT_MODEL = os.environ.get("VOITURE_AGENT_MODEL", "claude-opus-5-5")

# Repli automatique côté serveur si un modèle refuse une requête.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
USE_FALLBACKS = os.environ.get("VOITURE_FALLBACKS", "1") != "0"

# Garde-fous de coût pour une mission de recherche.
MAX_CHEF_TURNS = int(os.environ.get("VOITURE_MAX_CHEF_TURNS", "12"))
MAX_AGENT_CALLS = int(os.environ.get("VOITURE_MAX_AGENT_CALLS", "10"))

# Planificateur : désactivable (tests, ou si vous lancez les recherches à la main).
SCHEDULER_ENABLED = os.environ.get("VOITURE_SCHEDULER", "1") != "0"
SCHEDULER_TICK_SECONDS = int(os.environ.get("VOITURE_SCHEDULER_TICK", "300"))

# Notifications
VAPID_CONTACT = os.environ.get("VOITURE_VAPID_CONTACT", "mailto:admin@example.com")
NTFY_SERVER = os.environ.get("VOITURE_NTFY_SERVER", "https://ntfy.sh")

# Jeton d'accès à l'app (généré au premier lancement s'il est absent).
APP_TOKEN = os.environ.get("VOITURE_APP_TOKEN", "")
