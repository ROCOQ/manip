#!/usr/bin/env python3
"""Ma Nouvelle Voiture (stock Bretagne) : python3 mnv_collect.py <marque> ... (lit le JSON-LD des pages /bretagne/<marque>-occasion.html)."""
import json, re, sys, time, urllib.request
UA = "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
def fetch(u):
    req = urllib.request.Request(u, headers={"User-Agent": UA, "Accept-Language": "fr-FR"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read().decode("utf-8", "replace")
out = []
for brand in sys.argv[1:]:
    for page in range(1, 4):
        u = f"https://www.manouvellevoiture.com/bretagne/{brand}-occasion.html" + (f"?page={page}" if page > 1 else "")
        try:
            st, h = fetch(u)
        except Exception as e:
            print(brand, page, "erreur", e, file=sys.stderr); break
        items = []
        for b in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', h, re.S):
            try: d = json.loads(b)
            except Exception: continue
            for blk in (d if isinstance(d, list) else [d]):
                if blk.get("@type") == "ItemList":
                    items += [e["item"] for e in blk.get("itemListElement", [])]
        print(brand, page, st, len(items), file=sys.stderr)
        out += items
        if len(items) < 20: break
        time.sleep(1.5)
json.dump(out, sys.stdout, ensure_ascii=False)
