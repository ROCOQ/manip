#!/usr/bin/env python3
"""Vérifie des fichiers de jeux Wii U avant transfert sur iPad.

Détecte les formats (.wua, .wud, .wux, dossiers code/content/meta, .rpx),
contrôle la structure, le fichier keys.txt et la taille totale.
Aucune dépendance externe (Python 3.8+).

Usage :
    python3 tools/check_wiiu_files.py DOSSIER [--keys keys.txt] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional

WUD_SIZE = 25_025_314_816  # taille exacte d'une image disque Wii U
WUX_MAGIC = b"WUX0"
KEY_RE = re.compile(r"^[0-9a-fA-F]{32}$")
GiB = 1024 ** 3


@dataclass
class Title:
    path: str
    kind: str
    size: int
    needs_keys: bool = False
    issues: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


def dir_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def check_wud(path: Path) -> Title:
    t = Title(str(path), "wud", path.stat().st_size, needs_keys=True)
    if t.size != WUD_SIZE:
        t.issues.append(
            f"taille inattendue ({t.size} octets, attendu {WUD_SIZE}) : dump incomplet ?"
        )
    return t


def check_wux(path: Path) -> Title:
    t = Title(str(path), "wux", path.stat().st_size, needs_keys=True)
    with path.open("rb") as fh:
        if fh.read(4) != WUX_MAGIC:
            t.issues.append("en-tête WUX0 absent : fichier corrompu ou mal nommé")
    return t


def check_wua(path: Path) -> Title:
    t = Title(str(path), "wua", path.stat().st_size)
    if t.size < 1024 * 1024:
        t.issues.append("fichier .wua anormalement petit (< 1 Mo)")
    return t


def check_dump_dir(path: Path) -> Title:
    t = Title(str(path), "dossier code/content/meta", dir_size(path))
    code = path / "code"
    if not any(code.glob("*.rpx")):
        t.issues.append("aucun .rpx dans code/")
    for f in ("code/app.xml", "code/cos.xml", "meta/meta.xml"):
        if not (path / f).is_file():
            t.issues.append(f"fichier manquant : {f}")
    if not (path / "content").is_dir():
        t.issues.append("dossier content/ manquant")
    return t


def is_dump_dir(path: Path) -> bool:
    return (path / "code").is_dir() and (path / "meta").is_dir()


def scan(root: Path) -> List[Title]:
    """Parcourt root sans descendre dans les dossiers de dump déjà identifiés."""
    checkers = {".wud": check_wud, ".wux": check_wux, ".wua": check_wua}
    if is_dump_dir(root):
        return [check_dump_dir(root)]
    titles: List[Title] = []
    for dirpath, dirnames, filenames in os.walk(root):
        base = Path(dirpath)
        dirnames.sort()
        for d in list(dirnames):
            if is_dump_dir(base / d):
                titles.append(check_dump_dir(base / d))
                dirnames.remove(d)  # élagage : inutile d'explorer l'intérieur
        for name in sorted(filenames):
            f = base / name
            ext = f.suffix.lower()
            if ext in checkers:
                titles.append(checkers[ext](f))
            elif ext == ".rpx":
                titles.append(Title(str(f), "rpx isolé", f.stat().st_size,
                                    issues=["un .rpx seul ne suffit pas : copiez tout le dossier du jeu"]))
    return titles


def check_keys(path: Path) -> tuple[int, List[str]]:
    valid, problems = 0, []
    for n, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if KEY_RE.match(line):
            valid += 1
        else:
            problems.append(f"ligne {n} invalide : {raw.strip()[:40]!r}")
    return valid, problems


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dossier", type=Path)
    ap.add_argument("--keys", type=Path, help="chemin vers keys.txt")
    ap.add_argument("--json", action="store_true", help="sortie JSON")
    args = ap.parse_args(argv)

    if not args.dossier.exists():
        print(f"Erreur : {args.dossier} introuvable", file=sys.stderr)
        return 2

    titles = scan(args.dossier)
    keys_info = None
    if args.keys:
        if args.keys.is_file():
            keys_info = check_keys(args.keys)
        else:
            keys_info = (0, [f"{args.keys} introuvable"])

    needs_keys = any(t.needs_keys for t in titles)
    total = sum(t.size for t in titles)

    if args.json:
        print(json.dumps({
            "titles": [dict(asdict(t), ok=t.ok) for t in titles],
            "total_bytes": total,
            "keys": None if keys_info is None else {"valid": keys_info[0], "problems": keys_info[1]},
        }, indent=2, ensure_ascii=False))
    else:
        if not titles:
            print("Aucun jeu Wii U détecté.")
        for t in titles:
            mark = "OK " if t.ok else "!! "
            print(f"[{mark}] {t.kind:<26} {t.size / GiB:6.2f} Go  {t.path}")
            for i in t.issues:
                print(f"        - {i}")
        print(f"\nTotal : {len(titles)} jeu(x), {total / GiB:.2f} Go à transférer.")
        if needs_keys:
            if keys_info is None:
                print("Attention : des .wud/.wux sont présents, il faut un keys.txt (--keys) ou une conversion en .wua.")
            else:
                print(f"keys.txt : {keys_info[0]} clé(s) valide(s).")
        if keys_info:
            for p in keys_info[1]:
                print(f"  - keys.txt : {p}")
        if any(t.kind in ("wud", "wux") for t in titles):
            print("Conseil : convertissez en .wua avec Cemu (Title Manager), c'est plus léger et ça évite keys.txt.")

    bad = any(not t.ok for t in titles) or bool(keys_info and keys_info[1])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
