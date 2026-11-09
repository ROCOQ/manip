# manip — Jouer sur iPad (Wii U et Steam)

## 🆕 Votre bibliothèque Steam sur iPad, sans PC et gratuitement

Solution : **GeForce NOW (offre gratuite) dans Safari**, pour les jeux Steam
présents dans son catalogue. Sessions d'1 h, file d'attente, mais 0 € et aucun PC.

1. Guide complet et arbre de décision : [docs/steam/STEAM_IPAD.md](docs/steam/STEAM_IPAD.md)
2. Quels jeux de ma bibliothèque sont compatibles ?
   ```bash
   python3 tools/steam_cloud_check.py --library mes_jeux.txt
   # ou : STEAM_API_KEY=... python3 tools/steam_cloud_check.py --steamid 7656119XXXXXXXXXX
   ```
   (fonctionne aussi sur l'iPad dans l'app gratuite **a-Shell**)
3. Fluidité et dépannage : [docs/steam/FLUIDITE.md](docs/steam/FLUIDITE.md)
4. Agents : `steam-ipad-advisor`, `steam-library-checker`, `steam-cloud-troubleshooter`.

---

## Émulateur Wii U sur iPad

Ce dépôt sert de **kit de préparation** pour jouer à vos jeux Wii U sur iPad :
un guide d'installation, un script qui vérifie vos fichiers de jeux **avant** de
les envoyer sur l'iPad, et des agents Claude Code pour vous aider.

> ⚠️ Rien ici ne s'installe *tout seul* sur l'iPad : iOS n'autorise pas un dépôt
> Git à installer des applications. L'installation se fait à la main sur l'iPad
> (ou via un PC/Mac pour le sideload), en suivant [docs/INSTALLATION.md](docs/INSTALLATION.md).

## Les options en novembre 2026

| Émulateur | Base | Installation | Remarques |
|---|---|---|---|
| **Fin** | — | App Store ([lien](https://apps.apple.com/us/app/fin-game-emulator/id6758910777)) | iOS 17+. Multi-consoles (GC, Wii, Wii U, 3DS…). Le plus simple à installer. |
| **MeloCafe** | Port de Cemu | Sideload (AltStore / SideStore) | Sorti le 14/09/2026, du dev de MeloNX. Demande l'entitlement *increased memory limit* et probablement le JIT. |
| **MuffinEMU** | Cemu, open source | SideStore / AltStore / TrollStore ([site](https://muffinemu.github.io/MuffinEMU/)) | iOS 15+. Testé sur iPad Pro A12Z (infos du site du projet, non vérifiées de façon indépendante). |

👉 **Recommandation** : commencez par **Fin** (App Store, zéro bidouille). Si les
performances ou la compatibilité ne suffisent pas, passez à **MeloCafe**.

## Démarrage rapide

1. Lisez [docs/INSTALLATION.md](docs/INSTALLATION.md) et vérifiez que votre iPad est compatible.
2. Dumpez **vos propres** jeux depuis votre Wii U ([docs/DUMP_JEUX.md](docs/DUMP_JEUX.md)).
3. Vérifiez les fichiers sur votre ordinateur :
   ```bash
   python3 tools/check_wiiu_files.py /chemin/vers/mes_jeux --keys /chemin/vers/keys.txt
   ```
4. Copiez les jeux validés sur l'iPad (app **Fichiers**, AirDrop, câble USB-C ou clé USB).
5. En cas de souci : [docs/DEPANNAGE.md](docs/DEPANNAGE.md).
6. Fiche de mon iPad : [docs/MON_IPAD.md](docs/MON_IPAD.md).

## Agents Claude Code inclus

Dans `.claude/agents/` (utilisables avec Claude Code dans ce dépôt) :

- **`wiiu-ipad-setup`** — vous guide pas à pas selon votre modèle d'iPad et votre version d'iPadOS.
- **`wiiu-troubleshooter`** — diagnostique crash, écran noir, lenteurs, JIT, jeux non reconnus.
- **`wiiu-game-checker`** — lance le script de vérification et explique le rapport.

Exemple : *« Utilise l'agent wiiu-ipad-setup, j'ai un iPad Air M2 sous iPadOS 18 »*.

## Légalité

Utilisez uniquement des jeux et des clés **dumpés depuis votre propre console**.
Ce dépôt ne contient et ne fournira aucun jeu, ROM, clé ou firmware.

## Sources

- [Wii U Emulation Is Coming To iPad — Retro Dodo](https://retrododo.com/wii-u-emulation-is-coming-to-ipad/)
- [A Wii U Emulator Just Launched on iPhone — Held Games](https://heldgames.com/guides/melocafe-wii-u-emulator-iphone)
- [Wii U Emulation on Handhelds in 2026 — Held Games](https://heldgames.com/guides/wii-u-emulation-handheld)
- [MuffinEMU (site officiel)](https://muffinemu.github.io/MuffinEMU/)
- [Fin sur l'App Store](https://apps.apple.com/us/app/fin-game-emulator/id6758910777)
- [Wii U emulators — Emulation General Wiki](https://emulation.gametechwiki.com/index.php/Wii_U_emulators)
