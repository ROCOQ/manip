# Jouer à sa bibliothèque Steam sur iPad, sans PC et sans payer

> Vérifié en novembre 2026. Les offres de cloud gaming changent souvent : les
> agents de ce dépôt revérifient les conditions sur le web avant de conseiller.

## La réponse courte

**GeForce NOW, offre gratuite, dans Safari.** C'est aujourd'hui la seule façon
légale, gratuite et sans PC de lancer **vos propres jeux Steam** sur un iPad :
le jeu tourne sur un PC de NVIDIA, l'iPad ne reçoit que la vidéo.

| | Offre gratuite GeForce NOW |
|---|---|
| Prix | 0 € |
| Jeux | ceux que **vous possédez** sur Steam **et** qui sont dans le catalogue GFN (pas tous !) |
| Session | **1 heure**, puis retour dans la file d'attente (on peut relancer) |
| File d'attente | priorité la plus basse ; pubs possibles pendant l'attente (jusqu'à ~2 min) |
| Qualité | jusqu'à 1080p, matériel « de base » |
| Sur iPad | navigateur Safari (play.geforcenow.com), pas d'app App Store |

👉 Première étape : savoir **lesquels de vos jeux** sont compatibles, avec
`tools/steam_cloud_check.py` (voir plus bas) ou l'agent `steam-library-checker`.

## Arbre de décision

```
Le jeu est-il dans le catalogue GeForce NOW (version Steam) ?
├── Oui → GeForce NOW gratuit dans Safari .......................... § 1
└── Non
    ├── Un ami/proche possède le jeu et il est multijoueur local ?
    │   └── Steam Remote Play Together via l'app Steam Link ........... § 3
    ├── Un proche a un PC allumé avec Steam (même à distance) ?
    │   └── Steam Link depuis son PC ................................. § 3
    ├── Jeu DOS ou point-and-click ancien (SCUMM) ?
    │   └── iDOS 3 / ScummVM en local sur l'iPad ..................... § 4
    └── Sinon : pas de solution gratuite et légale aujourd'hui ........ § 5
```

## 1. Installer GeForce NOW sur l'iPad

1. Créez un compte gratuit NVIDIA sur **play.geforcenow.com** (depuis Safari).
2. Dans Safari, ouvrez **play.geforcenow.com**, touchez **Partager** →
   **Sur l'écran d'accueil**. Lancez ensuite GFN **depuis cette icône**
   (plein écran, meilleure gestion de la manette).
3. Connectez-vous, puis **Paramètres → Connexions → Steam** pour relier votre
   compte (synchronisation de la bibliothèque).
4. Choisissez l'offre **Gratuite** si on vous propose un abonnement.
5. Branchez une manette **avant** de lancer un jeu (voir § 2).
6. Ouvrez un jeu de votre bibliothèque → **Jouer**. La première fois, Steam
   vous demande vos identifiants **dans** la session cloud : cochez « Se
   souvenir de moi » et validez le Steam Guard sur votre téléphone.
7. Vos sauvegardes passent par **Steam Cloud** : elles sont conservées entre
   les sessions (et récupérables sur un PC plus tard). Pour un jeu sans Steam
   Cloud, la sauvegarde peut se perdre : vérifiez sur la page Steam du jeu.

### Bien vivre la limite d'1 heure

- **Sauvegardez vers 50 min** : GFN prévient avant la fin, mais pas toujours au bon moment.
- Jouez aux **heures creuses** (matin, début d'après-midi en semaine) : file d'attente plus courte.
- Pendant la file d'attente, laissez Safari **au premier plan**, sinon vous perdez votre place.
- Les jeux à sessions courtes (rogue-lite, course, combat, indé) sont idéaux.

## 2. Fluidité maximale

Le détail (réglages, réseau, dépannage) est dans [FLUIDITE.md](FLUIDITE.md). L'essentiel :

1. **Réseau** : Wi-Fi **5 GHz** près de la box, ou mieux **adaptateur USB-C →
   Ethernet** (fonctionne sur iPad Pro 2018 sans réglage). Il faut ≥ 15 Mb/s
   stables et un ping < 40 ms vers le serveur GFN.
2. **Manette Bluetooth** (Xbox Series, DualSense, DualShock 4, ou manette
   USB-C type Backbone/Kishi) : bien plus fiable que le tactile ou le clavier.
3. Dans GFN : **Paramètres → Qualité du flux** → « Équilibré » ou personnalisé
   1080p / 60 i/s, et lancez le **test réseau** intégré.
4. Sur l'iPad : mode Économie d'énergie **désactivé**, Bluetooth/AirDrop des
   autres appareils au calme, autres apps fermées, pas de VPN.

## 3. Jeux absents de GFN : passer par un proche (gratuit)

L'app **Steam Link** (App Store, gratuite) reçoit l'image d'un ordinateur qui
fait tourner Steam. Sans PC à vous, deux cas restent possibles :

- **Remote Play Together** : un ami lance un jeu multijoueur local qu'**il**
  possède et vous invite ; vous rejoignez depuis Steam Link sur l'iPad, sans
  posséder le jeu.
- **Le PC d'un proche** : avec Steam installé et allumé, il peut lancer votre
  jeu (via Steam Famille / partage de bibliothèque, ou votre compte) et vous le
  diffusez via Steam Link, même hors de son réseau local. Moins confortable,
  mais gratuit et sans limite d'1 h.

## 4. Jeux qui tournent directement sur l'iPad

Certains jeux Steam sont de vieux jeux DOS ou SCUMM « emballés » :

- **iDOS 3** (App Store) : jeux DOS fournis avec DOSBox sur Steam.
- **ScummVM** (App Store, gratuit) : Monkey Island, Day of the Tentacle,
  Broken Sword… (liste sur scummvm.org).

Il faut récupérer **une fois** les fichiers du jeu acheté (sur n'importe quel
ordinateur avec Steam, ou avec SteamCMD/DepotDownloader de votre propre compte)
puis les copier dans l'app via **Fichiers**. Aucun lien de téléchargement de
jeux n'est fourni ici.

Beaucoup de jeux Steam ont aussi une **version iOS** (Stardew Valley,
Terraria, Dead Cells, Slay the Spire, Balatro…), mais elle s'achète à part.

## 5. Ce qui ne marche pas (et pourquoi)

| Idée | Pourquoi non |
|---|---|
| Émuler Windows sur l'iPad (UTM SE, etc.) | Pas de JIT ni d'accélération 3D : même un jeu 2D est injouable. |
| Steam Link sans aucun PC | Steam Link n'exécute rien, il affiche un PC distant. |
| VM « cloud gratuite » (Oracle Free Tier, Colab…) | Pas de GPU, ou interdit par les conditions d'utilisation. |
| Xbox Cloud Gaming / Amazon Luna | Pas votre bibliothèque Steam, et payant (hors quelques free-to-play). |
| Shadow, Boosteroid, offres GFN payantes | Fonctionnent très bien… mais payants. À garder en tête si le gratuit frustre (GFN Performance : sessions 6 h, sans pub, file prioritaire). |
| Sites de comptes partagés ou « cloud gratuit illimité » | Arnaques ou vol de compte. À fuir. |

## 6. Vérifier sa bibliothèque : `tools/steam_cloud_check.py`

Le script compare vos jeux Steam avec le catalogue public GeForce NOW.

**Option A — liste à la main** : un titre ou un appid (ou une URL du magasin
Steam) par ligne dans `mes_jeux.txt`, puis :

```bash
python3 tools/steam_cloud_check.py --library mes_jeux.txt
```

**Option B — automatique avec l'API Steam** :

1. Rendez publics les **Détails des jeux** (Steam → Profil → Modifier le profil
   → Paramètres de confidentialité).
2. Créez une clé gratuite sur `steamcommunity.com/dev/apikey` (domaine :
   `localhost`). Ne la partagez jamais, ne la committez jamais.
3. Trouvez votre **SteamID64** (17 chiffres) dans l'URL de votre profil ou
   sur steamid.io.
4. Lancez :
   ```bash
   STEAM_API_KEY=VOTRE_CLE python3 tools/steam_cloud_check.py --steamid 7656119XXXXXXXXXX
   ```

**Sans ordinateur** : installez **a-Shell** (App Store, gratuit, contient
python3), copiez `steam_cloud_check.py` dans son dossier via l'app Fichiers,
puis lancez la même commande dans a-Shell.

Si le catalogue ne se télécharge pas, ouvrez l'URL affichée par le script dans
Safari, enregistrez le JSON, et ajoutez `--catalog fichier.json`.

## Agents Claude Code

- `steam-ipad-advisor` : choisit la meilleure solution pour chaque jeu et guide l'installation.
- `steam-library-checker` : lance le script et explique le résultat.
- `steam-cloud-troubleshooter` : lag, image floue, déconnexions, manette, file d'attente.

## Sources

- [GeForce NOW — Wikipédia](https://en.wikipedia.org/wiki/GeForce_Now)
- [GeForce NOW : pubs dans la file d'attente de l'offre gratuite — Engadget](https://www.engadget.com/nvidia-geforce-now-gets-pre-roll-ads-for-free-users-125754649.html)
- [Limite mensuelle de 100 h (offres payantes) — iPhone in Canada](https://www.iphoneincanada.ca/2025/12/25/geforce-nows-unlimited-gaming-era-ends-january-1/)
- [Installer GeForce NOW sur iPhone et iPad — iMore](https://imore.com/how-set-geforce-now-iphone-and-ipad)
- [Jouer à ses jeux Steam sur GeForce NOW — Android Central](https://www.androidcentral.com/can-i-play-my-steam-games-geforce-now)
