#!/usr/bin/env python3
"""Collecte d'annonces AutoScout24 (France) pour le Chasseur de voiture.

Lit les pages de résultats publiques d'AutoScout24 (données intégrées à la page),
sans contourner de protection, à faible volume (quelques pages par mission, avec pause).

Usage :
  python3 as24_collect.py --zip 35000 --rayon 150 --prix-max 18000 --annee-min 2022 \
      --km-max 50000 [--marque mazda --modele 3] [--garage j-bervas-rennes] [--pages 3] > annonces.json
  python3 as24_collect.py --photo URL_PHOTO --out /tmp/photos/a-xxx.jpg   # télécharge une photo

Sortie : liste JSON d'annonces normalisées (url, titre, prix, km, annee, energie, boite,
localisation, distance_km, vendeur, telephone, photos[], source).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request

BASE = "https://www.autoscout24.fr"
UA = ("Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")
NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def fetch(url: str, timeout: int = 30) -> tuple[str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.geturl(), resp.read().decode("utf-8", "replace")


def search_url(args, page: int) -> str:
    path = "/lst"
    if args.garage:
        path = f"/garages/{args.garage}"
    q = {"atype": "C", "cy": "F", "sort": "standard", "desc": "0", "ustate": "N,U", "page": str(page)}
    if not args.garage:
        q.update({"zip": args.zip, "zipr": str(args.rayon)})
        if args.marque:
            # Marque et modèle passent par leurs identifiants AutoScout24, seule façon de garder le rayon.
            make_id, model_id = taxonomy_ids(args.marque, args.modele)
            q["mmvmk0"] = make_id
            if model_id:
                q["mmvmd0"] = model_id
    if args.prix_max:
        q["priceto"] = str(args.prix_max)
    if args.annee_min:
        q["fregfrom"] = str(args.annee_min)
    if args.km_max:
        q["kmto"] = str(args.km_max)
    return BASE + path + "?" + urllib.parse.urlencode(q)


_TAXO: dict = {}


def taxonomy_ids(marque: str, modele: str | None) -> tuple[str, str | None]:
    """Identifiants AutoScout24 de la marque (et du modèle), lus sur une page de résultats nationale."""
    key = (marque, modele)
    if key in _TAXO:
        return _TAXO[key]
    path = f"/lst/{marque}" + (f"/{modele}" if modele else "")
    _, html = fetch(BASE + path + "?atype=C&cy=F")
    m = NEXT_DATA.search(html)
    listings = (json.loads(m.group(1))["props"]["pageProps"].get("listings") or []) if m else []
    make_id = model_id = None
    for it in listings:
        taxo = (it.get("tracking") or {}).get("modelTaxonomy") or ""
        r = re.search(r"make_id:(\d+)", taxo)
        if r:
            make_id = r.group(1)
            if modele:
                model_id = str((it.get("vehicle") or {}).get("modelId") or "") or None
            break
    if not make_id:
        raise SystemExit(f"Marque/modèle inconnu sur AutoScout24 : {path}")
    time.sleep(1)
    _TAXO[key] = (make_id, model_id)
    return _TAXO[key]


def big_photo(url: str) -> str:
    # Les vignettes finissent par /250x188.webp : on demande une taille plus grande.
    return re.sub(r"/\d+x\d+\.webp$", "/720x540.webp", url)


def normalize(item: dict) -> dict:
    v = item.get("vehicle") or {}
    loc = item.get("location") or {}
    seller = item.get("seller") or {}
    tracking = item.get("tracking") or {}
    details = {d.get("ariaLabel"): d.get("data") for d in item.get("vehicleDetails") or []}
    reg = tracking.get("firstRegistration") or details.get("1ère immatriculation") or ""
    year = re.search(r"(\d{4})", reg)
    km = re.sub(r"\D", "", str(tracking.get("mileage") or v.get("mileageInKm") or ""))
    phones = seller.get("phones") or []
    return {
        "url": BASE + item["url"] if str(item.get("url", "")).startswith("/") else item.get("url"),
        "titre": v.get("subtitle") or item.get("title"),
        "marque": v.get("make"),
        "modele": v.get("model"),
        "prix": (item.get("price") or {}).get("priceRaw"),
        "km": int(km) if km else None,
        "annee": int(year.group(1)) if year else None,
        "premiere_immatriculation": reg,
        "energie": v.get("fuel"),
        "boite": v.get("transmission"),
        "puissance": details.get("Puissance kW (CH)"),
        "localisation": " ".join(x for x in [loc.get("zip"), loc.get("city")] if x),
        "distance_km": loc.get("distanceToSearchLocationInKm"),
        "vendeur": seller.get("companyName") or seller.get("contactName") or seller.get("type"),
        "telephone": phones[0].get("formattedNumber") if phones else None,
        "photos": [big_photo(u) for u in (item.get("images") or [])[:4]],
        "evaluation_prix": (item.get("price") or {}).get("priceEvaluation"),
        "source": "autoscout24.fr",
    }


def collect(args) -> list[dict]:
    out, seen = [], set()
    for page in range(1, args.pages + 1):
        final, html = fetch(search_url(args, page))
        m = NEXT_DATA.search(html)
        if not m:
            break
        props = json.loads(m.group(1))["props"]["pageProps"]
        listings = props.get("listings") or []
        for it in listings:
            try:
                n = normalize(it)
            except Exception:
                continue
            if n["url"] and n["url"] not in seen:
                seen.add(n["url"])
                out.append(n)
        if page >= int(props.get("numberOfPages") or 1) or not listings:
            break
        time.sleep(2)
    return out


def check_alive(url: str) -> bool:
    """Une annonce retirée redirige vers une page de recherche (/lst/...)."""
    try:
        final, _ = fetch(url)
    except Exception:
        return False
    return "/offres/" in final


def detail(url: str) -> dict:
    """Détail d'une annonce : version exacte du moteur, équipements cités, garantie, photos."""
    final, html = fetch(url)
    if "/offres/" not in final:
        return {"url": url, "vivante": False}
    ld = json.loads(NEXT_DATA.search(html).group(1))["props"]["pageProps"]["listingDetails"]
    v = ld.get("vehicle") or {}
    desc = re.sub(r"<[^>]+>", " ", ld.get("description") or "")
    imgs = [i if isinstance(i, str) else (i.get("url") or "") for i in (ld.get("images") or [])]
    found = {k: bool(re.search(pat, desc, re.I)) for k, pat in {
        "carplay": r"carplay|apple car", "camera_recul": r"cam[ée]ra", "regulateur": r"r[ée]gulateur",
        "climatisation": r"\bclim|air conditionn"}.items()}
    return {
        "url": url, "vivante": True, "marque": v.get("make"), "modele": v.get("model"),
        "version": v.get("modelVersionInput"), "carrosserie": v.get("bodyType"), "couleur": v.get("bodyColor"),
        "premiere_immatriculation": v.get("firstRegistrationDate"), "km": v.get("mileageInKmRaw"),
        "garantie": ld.get("warranty"), "equipements_cites": found, "description": desc[:1500],
        "photos": [big_photo(i) for i in imgs[:4] if i],
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--zip", default="35000")
    p.add_argument("--rayon", type=int, default=150)
    p.add_argument("--prix-max", type=int)
    p.add_argument("--annee-min", type=int)
    p.add_argument("--km-max", type=int)
    p.add_argument("--marque")
    p.add_argument("--modele")
    p.add_argument("--garage", help="identifiant de la page vendeur AutoScout24, ex. j-bervas-rennes")
    p.add_argument("--pages", type=int, default=3)
    p.add_argument("--photo", help="URL d'une photo à télécharger")
    p.add_argument("--out", help="fichier de sortie pour --photo")
    p.add_argument("--verifier", help="URL d'annonce : affiche 'vivante' ou 'retiree'")
    p.add_argument("--detail", help="URL d'annonce : version du moteur, équipements, garantie, photos (JSON)")
    args = p.parse_args()

    if args.detail:
        json.dump(detail(args.detail), sys.stdout, ensure_ascii=False, indent=1)
        return
    if args.verifier:
        print("vivante" if check_alive(args.verifier) else "retiree")
        return
    if args.photo:
        req = urllib.request.Request(args.photo, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as resp, open(args.out, "wb") as f:
            f.write(resp.read())
        print(args.out)
        return
    json.dump(collect(args), sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
