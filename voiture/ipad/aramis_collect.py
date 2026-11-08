#!/usr/bin/env python3
"""Aramisauto : python3 aramis_collect.py <prix_max> <marque/modele> ... (lit le JSON-LD des pages modèle puis des fiches)."""
import json, re, sys, time, urllib.request
UA = "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
def fetch(u):
    req = urllib.request.Request(u, headers={"User-Agent": UA, "Accept-Language": "fr-FR"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.geturl(), r.read().decode("utf-8", "replace")
def ld_blocks(h):
    out = []
    for b in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', h, re.S):
        try: out.append(json.loads(b))
        except Exception: pass
    return out
res = []
maxp = int(sys.argv[1])
for path in sys.argv[2:]:
    try:
        final, h = fetch(f"https://www.aramisauto.com/voitures/{path}/")
    except Exception as e:
        print(path, "erreur", e, file=sys.stderr); continue
    items = []
    for d in ld_blocks(h):
        if d.get("@type") == "ItemList":
            items = [e["item"] for e in d.get("itemListElement", [])]
    cheap = [i for i in items if float((i.get("offers") or {}).get("price") or 1e9) <= maxp]
    print(path, len(items), "≤budget:", len(cheap), file=sys.stderr)
    for i in cheap:
        time.sleep(1.2)
        try:
            f2, h2 = fetch(i["url"])
        except Exception as e:
            print("  détail erreur", e, file=sys.stderr); continue
        car = next((d for d in ld_blocks(h2) if d.get("@type") in ("Car", "Vehicle", "Product")), {})
        txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h2))
        km = re.search(r"(\d[\d\s ]{2,7})\s?km", txt)
        yr = re.search(r"\b(20[12]\d)\b", i["name"] + " " + json.dumps(car))
        res.append({"name": i["name"], "url": i["url"], "price": i["offers"]["price"], "car": car,
                    "km_txt": km.group(1) if km else None})
    time.sleep(1.5)
json.dump(res, sys.stdout, ensure_ascii=False)
