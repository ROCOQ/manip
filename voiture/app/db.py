"""Mémoire persistante (SQLite) : profil, réglages, annonces, missions, chat."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

DEFAULT_PROFILE: dict[str, Any] = {
    "prenom": "",
    "localisation": "",
    "rayon_km": 100,
    "budget_max": None,
    "budget_ideal": None,
    "financement": "comptant",
    "usage": "mixte",
    "km_par_an": 15000,
    "nb_places": 5,
    "carrosseries": [],
    "energies": [],
    "boite": "peu importe",
    "annee_min": None,
    "km_max": None,
    "marques_preferees": [],
    "marques_exclues": [],
    "modeles_envisages": [],
    "equipements_indispensables": [],
    "criteres_redhibitoires": [],
    "vendeur": "peu importe",
    "recharge_domicile": False,
    "notes_libres": "",
}

DEFAULT_SETTINGS: dict[str, Any] = {
    "recherche_auto": True,
    "frequence_heures": 24,
    "seuil_notification": 75,
    "ntfy_topic": "",
    "agents_actifs": ["profil", "annonces", "concessions", "fiabilite", "prix", "couts", "verif"],
}

LISTING_STATUSES = ("nouvelle", "vue", "favori", "rejetee")
DEALER_STATUSES = ("nouvelle", "suivie", "ignoree")

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    titre TEXT, prix INTEGER, km INTEGER, annee INTEGER,
    energie TEXT, boite TEXT, localisation TEXT, source TEXT, vendeur TEXT,
    image_url TEXT, description TEXT,
    score INTEGER, verdict TEXT, analyse TEXT,
    statut TEXT NOT NULL DEFAULT 'nouvelle',
    feedback TEXT,
    notifie INTEGER NOT NULL DEFAULT 0,
    first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
    run_id INTEGER
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    declencheur TEXT NOT NULL,
    statut TEXT NOT NULL,
    debut TEXT NOT NULL, fin TEXT,
    rapport TEXT, journal TEXT NOT NULL DEFAULT '[]',
    erreur TEXT,
    tokens_entree INTEGER NOT NULL DEFAULT 0,
    tokens_sortie INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS chat (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL, content TEXT NOT NULL, ts TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS push_subscriptions (
    endpoint TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS concessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cle TEXT NOT NULL UNIQUE,
    nom TEXT NOT NULL,
    type TEXT, marques TEXT,
    adresse TEXT, ville TEXT, distance_km REAL,
    telephone TEXT, site TEXT, url_stock TEXT,
    note_avis REAL, nb_avis INTEGER,
    specialites TEXT, commentaire TEXT,
    statut TEXT NOT NULL DEFAULT 'nouvelle',
    notes_utilisateur TEXT,
    origine TEXT NOT NULL DEFAULT 'agent',
    created TEXT NOT NULL, updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memoire (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    note TEXT NOT NULL, ts TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_url(url: str) -> str:
    """Clé de dédoublonnage : sans fragment, sans paramètres de suivi, sans / final."""
    url = (url or "").strip()
    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        return url
    query = "&".join(
        p for p in parts.query.split("&")
        if p and not p.lower().startswith(("utm_", "xtor", "fbclid", "gclid"))
    )
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def _to_float(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", ".")
    num = "".join(ch for ch in text if ch.isdigit() or ch == ".")
    try:
        return float(num.strip(".")) if num.strip(".") else None
    except ValueError:
        return None


def _http_url(value: Any) -> str | None:
    url = str(value or "").strip()
    if not url:
        return None
    if not url.startswith(("http://", "https://")) and "." in url and " " not in url:
        url = "https://" + url
    return url if url.startswith(("http://", "https://")) else None


def _norm_text(value: Any) -> str:
    import unicodedata

    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower()
    return " ".join("".join(ch if ch.isalnum() else " " for ch in text).split())


def dealer_key(data: dict) -> str | None:
    """Clé de dédoublonnage d'une concession : nom + ville (ou, à défaut, domaine du site)."""
    nom = _norm_text(data.get("nom"))
    if not nom:
        return None
    ville = _norm_text(data.get("ville"))
    if ville:
        return f"{nom}|{ville}"
    site = _http_url(data.get("site"))
    return f"{nom}|{urlsplit(site).netloc.removeprefix('www.')}" if site else nom


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return int(digits) if digits else None


class Store:
    def __init__(self, path: Path | str):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __del__(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    # ---------- utilitaires ----------
    def _exec(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def _all(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def _one(self, sql: str, params: tuple = ()) -> dict | None:
        with self._lock:
            row = self._conn.execute(sql, params).fetchone()
            return dict(row) if row else None

    # ---------- clé / valeur ----------
    def get_kv(self, key: str, default: Any = None) -> Any:
        row = self._one("SELECT value FROM kv WHERE key = ?", (key,))
        return json.loads(row["value"]) if row else default

    def set_kv(self, key: str, value: Any) -> None:
        self._exec(
            "INSERT INTO kv(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value, ensure_ascii=False)),
        )

    def get_profile(self) -> dict:
        return {**DEFAULT_PROFILE, **self.get_kv("profile", {})}

    def update_profile(self, patch: dict) -> dict:
        profile = self.get_profile()
        for key, value in (patch or {}).items():
            if key in DEFAULT_PROFILE:
                profile[key] = value
        self.set_kv("profile", profile)
        return profile

    def profile_is_empty(self) -> bool:
        p = self.get_profile()
        return not (p.get("budget_max") or p.get("modeles_envisages") or p.get("carrosseries") or p.get("notes_libres"))

    def get_settings(self) -> dict:
        return {**DEFAULT_SETTINGS, **self.get_kv("settings", {})}

    def update_settings(self, patch: dict) -> dict:
        settings = self.get_settings()
        for key, value in (patch or {}).items():
            if key in DEFAULT_SETTINGS:
                settings[key] = value
        settings["frequence_heures"] = max(1, int(settings["frequence_heures"] or 24))
        settings["seuil_notification"] = min(100, max(0, int(settings["seuil_notification"] or 0)))
        self.set_kv("settings", settings)
        return settings

    # ---------- mémoire du chef ----------
    def add_memory(self, note: str) -> None:
        note = (note or "").strip()
        if note:
            self._exec("INSERT INTO memoire(note, ts) VALUES(?, ?)", (note[:1000], now()))

    def memories(self, limit: int = 50) -> list[dict]:
        return self._all("SELECT * FROM memoire ORDER BY id DESC LIMIT ?", (limit,))

    def delete_memory(self, memory_id: int) -> None:
        self._exec("DELETE FROM memoire WHERE id = ?", (memory_id,))

    # ---------- annonces ----------
    def upsert_listing(self, data: dict, run_id: int | None = None) -> tuple[int, bool] | None:
        """Ajoute ou met à jour une annonce. Renvoie (id, nouvelle?) ou None si l'URL est invalide."""
        url = normalize_url(str(data.get("url") or ""))
        if not url.startswith(("http://", "https://")):
            return None
        fields = {
            "titre": (data.get("titre") or "")[:300] or None,
            "prix": _to_int(data.get("prix")),
            "km": _to_int(data.get("km")),
            "annee": _to_int(data.get("annee")),
            "energie": data.get("energie") or None,
            "boite": data.get("boite") or None,
            "localisation": data.get("localisation") or None,
            "source": data.get("source") or urlsplit(url).netloc,
            "vendeur": data.get("vendeur") or None,
            "image_url": data.get("image_url") or None,
            "description": (data.get("description") or "")[:2000] or None,
        }
        existing = self._one("SELECT id FROM listings WHERE url = ?", (url,))
        ts = now()
        if existing:
            sets = ", ".join(f"{k} = COALESCE(?, {k})" for k in fields)
            self._exec(
                f"UPDATE listings SET {sets}, last_seen = ? WHERE id = ?",
                (*fields.values(), ts, existing["id"]),
            )
            return existing["id"], False
        cols = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        cur = self._exec(
            f"INSERT INTO listings(url, {cols}, first_seen, last_seen, run_id) VALUES(?, {marks}, ?, ?, ?)",
            (url, *fields.values(), ts, ts, run_id),
        )
        return cur.lastrowid, True

    def score_listing(self, url: str, score: Any, verdict: str | None, analyse: dict | None) -> bool:
        url = normalize_url(url)
        s = _to_int(score)
        if s is not None:
            s = max(0, min(100, s))
        cur = self._exec(
            "UPDATE listings SET score = COALESCE(?, score), verdict = COALESCE(?, verdict), "
            "analyse = COALESCE(?, analyse) WHERE url = ?",
            (s, verdict, json.dumps(analyse, ensure_ascii=False) if analyse else None, url),
        )
        return cur.rowcount > 0

    def get_listing(self, listing_id: int) -> dict | None:
        row = self._one("SELECT * FROM listings WHERE id = ?", (listing_id,))
        return self._decode_listing(row) if row else None

    def list_listings(self, statut: str | None = None, limit: int = 200) -> list[dict]:
        if statut:
            rows = self._all(
                "SELECT * FROM listings WHERE statut = ? ORDER BY COALESCE(score, -1) DESC, id DESC LIMIT ?",
                (statut, limit),
            )
        else:
            rows = self._all(
                "SELECT * FROM listings WHERE statut != 'rejetee' "
                "ORDER BY COALESCE(score, -1) DESC, id DESC LIMIT ?",
                (limit,),
            )
        return [self._decode_listing(r) for r in rows]

    @staticmethod
    def _decode_listing(row: dict) -> dict:
        if row.get("analyse"):
            try:
                row["analyse"] = json.loads(row["analyse"])
            except json.JSONDecodeError:
                pass
        return row

    def set_listing_status(self, listing_id: int, statut: str, feedback: str | None = None) -> dict | None:
        if statut not in LISTING_STATUSES:
            raise ValueError(f"statut inconnu : {statut}")
        self._exec(
            "UPDATE listings SET statut = ?, feedback = COALESCE(?, feedback) WHERE id = ?",
            (statut, feedback, listing_id),
        )
        listing = self.get_listing(listing_id)
        if listing and feedback:
            label = "aimée" if statut == "favori" else "rejetée" if statut == "rejetee" else statut
            self.add_memory(f"Annonce {label} « {listing.get('titre') or listing['url']} » : {feedback}")
        return listing

    def known_listings_digest(self, limit: int = 80) -> list[dict]:
        """Résumé compact des annonces déjà connues, pour que les agents ne les reproposent pas."""
        rows = self._all(
            "SELECT url, titre, prix, km, annee, score, statut, feedback FROM listings "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return rows

    def listings_to_notify(self, seuil: int) -> list[dict]:
        return self._all(
            "SELECT * FROM listings WHERE notifie = 0 AND statut = 'nouvelle' AND score >= ? "
            "ORDER BY score DESC",
            (seuil,),
        )

    def mark_notified(self, ids: list[int]) -> None:
        for listing_id in ids:
            self._exec("UPDATE listings SET notifie = 1 WHERE id = ?", (listing_id,))

    # ---------- missions ----------
    def start_run(self, declencheur: str) -> int:
        cur = self._exec(
            "INSERT INTO runs(declencheur, statut, debut) VALUES(?, 'en_cours', ?)",
            (declencheur, now()),
        )
        return cur.lastrowid

    def append_journal(self, run_id: int, entry: dict) -> None:
        with self._lock:
            row = self._one("SELECT journal FROM runs WHERE id = ?", (run_id,))
            journal = json.loads(row["journal"]) if row else []
            journal.append({"ts": now(), **entry})
            self._exec("UPDATE runs SET journal = ? WHERE id = ?", (json.dumps(journal, ensure_ascii=False), run_id))

    def add_usage(self, run_id: int, tokens_in: int, tokens_out: int) -> None:
        self._exec(
            "UPDATE runs SET tokens_entree = tokens_entree + ?, tokens_sortie = tokens_sortie + ? WHERE id = ?",
            (tokens_in, tokens_out, run_id),
        )

    def finish_run(self, run_id: int, statut: str, rapport: dict | None = None, erreur: str | None = None) -> None:
        self._exec(
            "UPDATE runs SET statut = ?, fin = ?, rapport = ?, erreur = ? WHERE id = ?",
            (statut, now(), json.dumps(rapport, ensure_ascii=False) if rapport else None, erreur, run_id),
        )

    def fail_stale_runs(self) -> None:
        """Au redémarrage, une mission « en cours » a forcément été interrompue."""
        self._exec("UPDATE runs SET statut = 'interrompue', fin = ? WHERE statut = 'en_cours'", (now(),))

    def get_run(self, run_id: int) -> dict | None:
        row = self._one("SELECT * FROM runs WHERE id = ?", (run_id,))
        return self._decode_run(row) if row else None

    def list_runs(self, limit: int = 20) -> list[dict]:
        return [self._decode_run(r) for r in self._all("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,))]

    def last_finished_run(self) -> dict | None:
        row = self._one("SELECT * FROM runs WHERE statut = 'terminee' ORDER BY id DESC LIMIT 1")
        return self._decode_run(row) if row else None

    def last_run_start(self) -> str | None:
        row = self._one("SELECT debut FROM runs WHERE declencheur = 'auto' OR statut = 'terminee' ORDER BY id DESC LIMIT 1")
        return row["debut"] if row else None

    @staticmethod
    def _decode_run(row: dict) -> dict:
        row["rapport"] = json.loads(row["rapport"]) if row.get("rapport") else None
        row["journal"] = json.loads(row["journal"]) if row.get("journal") else []
        return row

    # ---------- chat ----------
    def add_chat(self, role: str, content: str) -> None:
        self._exec("INSERT INTO chat(role, content, ts) VALUES(?, ?, ?)", (role, content, now()))

    def chat_history(self, limit: int = 40) -> list[dict]:
        rows = self._all("SELECT * FROM chat ORDER BY id DESC LIMIT ?", (limit,))
        return list(reversed(rows))

    def clear_chat(self) -> None:
        self._exec("DELETE FROM chat")

    # ---------- concessions ----------
    def upsert_dealer(self, data: dict, origine: str = "agent") -> tuple[int, bool] | None:
        """Ajoute ou complète une concession. Renvoie (id, nouvelle?) ou None si le nom manque."""
        key = dealer_key(data)
        if not key:
            return None
        marques = data.get("marques")
        if isinstance(marques, str):
            marques = [m.strip() for m in marques.split(",") if m.strip()]
        fields = {
            "nom": str(data.get("nom")).strip()[:200],
            "type": (data.get("type") or None),
            "marques": json.dumps(marques, ensure_ascii=False) if marques else None,
            "adresse": data.get("adresse") or None,
            "ville": data.get("ville") or None,
            "distance_km": _to_float(data.get("distance_km")),
            "telephone": (str(data["telephone"]).strip() if data.get("telephone") else None),
            "site": _http_url(data.get("site")),
            "url_stock": _http_url(data.get("url_stock")),
            "note_avis": _to_float(data.get("note_avis")),
            "nb_avis": _to_int(data.get("nb_avis")),
            "specialites": data.get("specialites") or None,
            "commentaire": (data.get("commentaire") or data.get("pourquoi") or None),
        }
        if fields["note_avis"] is not None and not 0 <= fields["note_avis"] <= 5:
            fields["note_avis"] = None
        existing = self._one("SELECT id FROM concessions WHERE cle = ?", (key,))
        ts = now()
        if existing:
            sets = ", ".join(f"{k} = COALESCE(?, {k})" for k in fields)
            self._exec(f"UPDATE concessions SET {sets}, updated = ? WHERE id = ?",
                       (*fields.values(), ts, existing["id"]))
            return existing["id"], False
        statut = "suivie" if origine == "utilisateur" else "nouvelle"
        cols = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        cur = self._exec(
            f"INSERT INTO concessions(cle, {cols}, statut, origine, created, updated) "
            f"VALUES(?, {marks}, ?, ?, ?, ?)",
            (key, *fields.values(), statut, origine, ts, ts),
        )
        return cur.lastrowid, True

    @staticmethod
    def _decode_dealer(row: dict) -> dict:
        row["marques"] = json.loads(row["marques"]) if row.get("marques") else []
        return row

    def get_dealer(self, dealer_id: int) -> dict | None:
        row = self._one("SELECT * FROM concessions WHERE id = ?", (dealer_id,))
        return self._decode_dealer(row) if row else None

    def list_dealers(self, statut: str | None = None) -> list[dict]:
        order = ("ORDER BY CASE statut WHEN 'suivie' THEN 0 ELSE 1 END, "
                 "COALESCE(distance_km, 9999), COALESCE(note_avis, 0) DESC, id")
        if statut:
            rows = self._all(f"SELECT * FROM concessions WHERE statut = ? {order}", (statut,))
        else:
            rows = self._all(f"SELECT * FROM concessions WHERE statut != 'ignoree' {order}")
        return [self._decode_dealer(r) for r in rows]

    def set_dealer_status(self, dealer_id: int, statut: str, notes: str | None = None) -> dict | None:
        if statut not in DEALER_STATUSES:
            raise ValueError(f"statut inconnu : {statut}")
        self._exec(
            "UPDATE concessions SET statut = ?, notes_utilisateur = COALESCE(?, notes_utilisateur), updated = ? "
            "WHERE id = ?",
            (statut, notes, now(), dealer_id),
        )
        dealer = self.get_dealer(dealer_id)
        if dealer and notes:
            label = "suivie" if statut == "suivie" else "écartée" if statut == "ignoree" else statut
            self.add_memory(f"Concession {label} « {dealer['nom']} » : {notes}")
        return dealer

    def delete_dealer(self, dealer_id: int) -> bool:
        return self._exec("DELETE FROM concessions WHERE id = ?", (dealer_id,)).rowcount > 0

    def dealers_digest(self, limit: int = 40) -> list[dict]:
        """Résumé des concessions connues pour les agents (sans les concessions écartées)."""
        keys = ("id", "nom", "type", "marques", "ville", "distance_km", "site", "url_stock", "statut", "notes_utilisateur")
        return [{k: d.get(k) for k in keys if d.get(k)} for d in self.list_dealers()[:limit]]

    # ---------- abonnements push ----------
    def add_push_subscription(self, subscription: dict) -> None:
        endpoint = subscription.get("endpoint")
        if not endpoint:
            raise ValueError("abonnement sans endpoint")
        self._exec(
            "INSERT INTO push_subscriptions(endpoint, data, created) VALUES(?, ?, ?) "
            "ON CONFLICT(endpoint) DO UPDATE SET data = excluded.data",
            (endpoint, json.dumps(subscription), now()),
        )

    def push_subscriptions(self) -> list[dict]:
        return [json.loads(r["data"]) for r in self._all("SELECT data FROM push_subscriptions")]

    def remove_push_subscription(self, endpoint: str) -> None:
        self._exec("DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,))
