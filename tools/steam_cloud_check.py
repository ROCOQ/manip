#!/usr/bin/env python3
"""Indique quels jeux de votre bibliothèque Steam sont jouables en cloud (GeForce NOW).

Compare votre bibliothèque Steam avec le catalogue public de GeForce NOW,
d'abord par identifiant Steam (appid), puis par titre normalisé.
Aucune dépendance externe (Python 3.8+). Fonctionne aussi sur iPad dans
l'app gratuite « a-Shell » (App Store), qui inclut python3.

Sources possibles pour la bibliothèque (une seule) :
  --library FICHIER       liste texte (un titre ou un appid par ligne), CSV
                          (colonnes appid et/ou name) ou JSON renvoyé par
                          l'API Steam GetOwnedGames
  --steamid ID --api-key CLE
                          télécharge la liste via l'API Web Steam (clé
                          gratuite : https://steamcommunity.com/dev/apikey).
                          La clé peut aussi venir de la variable STEAM_API_KEY.

Catalogue GeForce NOW :
  par défaut téléchargé depuis l'URL publique de NVIDIA ; sinon
  --catalog FICHIER.json (copie locale enregistrée depuis un navigateur).

Usage :
    python3 tools/steam_cloud_check.py --library mes_jeux.txt
    python3 tools/steam_cloud_check.py --steamid 7656119... --api-key XXXX --json
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

GFN_CATALOG_URL = (
    "https://static.nvidiagrid.net/supported-public-game-list/locales/gfnpc-en-US.json"
)
STEAM_OWNED_URL = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
APP_RE = re.compile(r"/app/(\d+)")
STEAMID_RE = re.compile(r"^\d{17}$")
NOISE_RE = re.compile(
    r"\b(the|edition|definitive|remastered|goty|game of the year|deluxe|complete|"
    r"enhanced|director'?s cut|anniversary|ultimate|standard)\b"
)


@dataclass
class Game:
    name: str
    appid: Optional[int] = None
    playtime_min: int = 0


@dataclass
class CatalogEntry:
    title: str
    appid: Optional[int] = None
    store: str = ""
    status: str = ""
    optimized: bool = False


@dataclass
class Result:
    name: str
    appid: Optional[int]
    playtime_h: float
    on_gfn: bool
    match: str = ""  # "appid", "titre" ou ""
    gfn_title: str = ""
    store: str = ""
    notes: List[str] = field(default_factory=list)


def normalize(title: str) -> str:
    """Titre comparable : sans accents, ™/®, ponctuation ni mots de bruit."""
    t = unicodedata.normalize("NFKD", title)
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = t.replace("&", " and ")
    t = re.sub(r"[™®©]", "", t)
    t = re.sub(r"[^a-z0-9' ]+", " ", t)
    t = NOISE_RE.sub(" ", t)
    t = t.replace("'", "")
    return " ".join(t.split())


# --------------------------------------------------------------------------
# Lecture de la bibliothèque


def _games_from_json(data) -> List[Game]:
    if isinstance(data, dict):
        data = data.get("response", data)
        data = data.get("games", []) if isinstance(data, dict) else data
    games = []
    for g in data or []:
        if isinstance(g, dict):
            appid = g.get("appid")
            games.append(
                Game(
                    name=str(g.get("name") or f"appid {appid}"),
                    appid=int(appid) if appid is not None else None,
                    playtime_min=int(g.get("playtime_forever") or 0),
                )
            )
        else:
            games.extend(_games_from_lines([str(g)]))
    return games


def _games_from_lines(lines: Iterable[str]) -> List[Game]:
    games = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = APP_RE.search(line)
        if m:
            games.append(Game(name=f"appid {m.group(1)}", appid=int(m.group(1))))
        elif line.isdigit():
            games.append(Game(name=f"appid {line}", appid=int(line)))
        else:
            games.append(Game(name=line))
    return games


def _games_from_csv(text: str) -> List[Game]:
    reader = csv.DictReader(io.StringIO(text))
    cols = {c.lower().strip(): c for c in (reader.fieldnames or [])}
    id_col = cols.get("appid") or cols.get("app_id") or cols.get("id")
    name_col = cols.get("name") or cols.get("title") or cols.get("nom")
    games = []
    for row in reader:
        appid = (row.get(id_col) or "").strip() if id_col else ""
        name = (row.get(name_col) or "").strip() if name_col else ""
        if not appid and not name:
            continue
        games.append(
            Game(
                name=name or f"appid {appid}",
                appid=int(appid) if appid.isdigit() else None,
            )
        )
    return games


def load_library(path: Path) -> List[Game]:
    text = path.read_text(encoding="utf-8-sig")
    stripped = text.lstrip()
    if stripped.startswith(("{", "[")):
        return _games_from_json(json.loads(text))
    first = stripped.splitlines()[0].lower() if stripped else ""
    if path.suffix.lower() == ".csv" or ("," in first and re.search(r"appid|name|title|nom", first)):
        return _games_from_csv(text)
    return _games_from_lines(text.splitlines())


def fetch_owned_games(steamid: str, api_key: str, timeout: int = 30) -> List[Game]:
    if not STEAMID_RE.match(steamid):
        raise ValueError(
            "SteamID64 attendu (17 chiffres, ex. 7656119...). "
            "Trouvez-le sur steamid.io ou dans l'URL de votre profil."
        )
    query = urllib.parse.urlencode(
        {"key": api_key, "steamid": steamid, "include_appinfo": 1,
         "include_played_free_games": 1, "format": "json"}
    )
    with urllib.request.urlopen(f"{STEAM_OWNED_URL}?{query}", timeout=timeout) as resp:
        data = json.load(resp)
    games = _games_from_json(data)
    if not games:
        raise ValueError(
            "Aucun jeu renvoyé : le profil Steam ou le détail des jeux est sans doute "
            "privé (Steam > Profil > Modifier > Confidentialité > Détails des jeux : Public)."
        )
    return games


# --------------------------------------------------------------------------
# Catalogue GeForce NOW


def parse_catalog(data) -> List[CatalogEntry]:
    if isinstance(data, dict):
        for key in ("games", "data", "items", "apps"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    entries = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("name") or "").strip()
        if not title:
            continue
        appid = None
        for k, v in item.items():
            if isinstance(v, str) and "url" in k.lower():
                m = APP_RE.search(v)
                if m and "steam" in v.lower():
                    appid = int(m.group(1))
                    break
        if appid is None and str(item.get("steamAppId", "")).isdigit():
            appid = int(item["steamAppId"])
        entries.append(
            CatalogEntry(
                title=title,
                appid=appid,
                store=str(item.get("store") or ""),
                status=str(item.get("status") or ""),
                optimized=bool(item.get("isFullyOptimized")),
            )
        )
    return entries


def load_catalog(path: Optional[Path], timeout: int = 30) -> List[CatalogEntry]:
    if path:
        return parse_catalog(json.loads(path.read_text(encoding="utf-8-sig")))
    req = urllib.request.Request(GFN_CATALOG_URL, headers={"User-Agent": "manip-steam-cloud-check"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return parse_catalog(json.load(resp))


# --------------------------------------------------------------------------
# Comparaison


def compare(games: List[Game], catalog: List[CatalogEntry]) -> List[Result]:
    usable = [e for e in catalog if not e.status or e.status.upper() == "AVAILABLE"]
    steam_entries = [e for e in usable if not e.store or "steam" in e.store.lower()]
    by_appid: Dict[int, CatalogEntry] = {e.appid: e for e in steam_entries if e.appid}
    by_title: Dict[str, CatalogEntry] = {}
    for e in steam_entries:
        by_title.setdefault(normalize(e.title), e)

    results = []
    for g in games:
        r = Result(g.name, g.appid, round(g.playtime_min / 60, 1), on_gfn=False)
        entry = by_appid.get(g.appid) if g.appid else None
        if entry:
            r.match = "appid"
        elif not g.name.startswith("appid "):
            entry = by_title.get(normalize(g.name))
            if entry:
                r.match = "titre"
                r.notes.append("trouvé par le titre : vérifiez dans l'app que c'est bien la version Steam")
        if entry:
            r.on_gfn = True
            r.gfn_title = entry.title
            r.store = entry.store
            if r.name.startswith("appid "):
                r.name = entry.title
        results.append(r)
    results.sort(key=lambda r: (not r.on_gfn, -r.playtime_h, r.name.lower()))
    return results


def render(results: List[Result]) -> str:
    ok = [r for r in results if r.on_gfn]
    ko = [r for r in results if not r.on_gfn]
    out = [f"{len(ok)}/{len(results)} jeux de votre bibliothèque sont sur GeForce NOW.", ""]
    if ok:
        out.append("✅ Jouables sur iPad via GeForce NOW (gratuit, sessions d'1 h) :")
        for r in ok:
            hours = f" — {r.playtime_h} h jouées" if r.playtime_h else ""
            flag = " (correspondance par titre)" if r.match == "titre" else ""
            out.append(f"  • {r.name}{hours}{flag}")
        out.append("")
    if ko:
        out.append("❌ Absents du catalogue (voir docs/steam/STEAM_IPAD.md, section « Plan B ») :")
        for r in ko:
            out.append(f"  • {r.name}")
        out.append("")
    out.append("Le catalogue change chaque semaine : relancez le script de temps en temps.")
    return "\n".join(out)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--library", type=Path, help="fichier texte, CSV ou JSON de vos jeux")
    src.add_argument("--steamid", help="SteamID64 (17 chiffres) pour l'API Web Steam")
    p.add_argument("--api-key", default=os.environ.get("STEAM_API_KEY"),
                   help="clé API Web Steam (ou variable STEAM_API_KEY)")
    p.add_argument("--catalog", type=Path, help="copie locale du catalogue GeForce NOW (JSON)")
    p.add_argument("--json", action="store_true", help="sortie JSON")
    args = p.parse_args(argv)

    try:
        if args.steamid:
            if not args.api_key:
                p.error("--api-key (ou STEAM_API_KEY) est requis avec --steamid")
            games = fetch_owned_games(args.steamid, args.api_key)
        else:
            games = load_library(args.library)
        catalog = load_catalog(args.catalog)
    except (OSError, ValueError) as exc:  # URLError hérite d'OSError
        print(f"Erreur : {exc}", file=sys.stderr)
        if not args.catalog:
            print(
                "Astuce : si le téléchargement du catalogue échoue, ouvrez "
                f"{GFN_CATALOG_URL} dans un navigateur, enregistrez la page puis "
                "relancez avec --catalog fichier.json",
                file=sys.stderr,
            )
        return 2
    if not games:
        print("Erreur : aucun jeu lu dans la bibliothèque.", file=sys.stderr)
        return 2
    if not catalog:
        print("Erreur : catalogue GeForce NOW vide ou format inconnu.", file=sys.stderr)
        return 2

    results = compare(games, catalog)
    if args.json:
        print(json.dumps(
            {"total": len(results), "on_gfn": sum(r.on_gfn for r in results),
             "games": [asdict(r) for r in results]},
            ensure_ascii=False, indent=2))
    else:
        print(render(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
