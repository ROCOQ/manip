# 🚗 Chasseur de voiture : votre équipe d'agents IA

Une app pour **iPhone et Mac** qui cherche votre prochaine voiture à votre place.
Un **chef d'équipe IA** dirige sept **agents spécialisés**, recoupe leurs rapports, classe les
annonces et **vous prévient** quand une bonne affaire apparaît. Les recherches **continuent quand
l'app est fermée**, selon votre profil et vos réponses, qui sont toutes mémorisées.

## L'équipe

| Agent | Rôle |
|---|---|
| 🧑‍✈️ **Chef d'équipe** | Reçoit votre profil et la mémoire, donne les consignes, recoupe les rapports, note chaque annonce sur 100, publie la synthèse et décide s'il faut vous notifier. C'est aussi lui qui vous répond dans l'onglet *Chef*. |
| 🧭 **Conseiller besoins** | Traduit vos besoins en critères concrets et propose les modèles adaptés (avec motorisations et années). |
| 🔎 **Chasseur d'annonces** | Cherche des annonces réelles et actuelles (La Centrale, Leboncoin, AutoScout24, L'argus, ParuVendu, Aramisauto, Spoticar…). |
| 🏢 **Repéreur de concessions** | Recense les concessions officielles, labels occasion (Renew, Spoticar, Toyota Occasions…) et garages bien notés de votre secteur : adresse, distance, téléphone, site, page du stock, avis. |
| 🛠️ **Expert fiabilité** | Défauts connus, rappels constructeur, motorisations à éviter, points à vérifier à l'essai. |
| 💶 **Analyste prix** | Estime la cote de chaque annonce, repère les bonnes affaires et les prix suspects, donne une marge de négociation. |
| 🧮 **Comptable auto** | Coût annuel réel : énergie, assurance, entretien, carte grise, malus, Crit'Air / ZFE, aides possibles. |
| 🕵️ **Détective anti-arnaque** | Signaux d'alerte, questions à poser au vendeur, documents à demander (Histovec, CT, non-gage…). |

Chaque agent est un appel à Claude (modèle `claude-opus-5-5` par défaut) avec son propre rôle, la
**recherche web** et la **lecture de pages** côté Anthropic, et un rapport structuré. Le chef les
consulte via un outil ; plusieurs agents peuvent travailler **en parallèle**.

### Ce que l'app mémorise (base SQLite sur le serveur)

- votre **profil** (budget, zone, usage, km/an, énergies, carrosseries, marques, critères rédhibitoires…) ;
- vos **réglages** (fréquence des recherches, seuil de notification, agents actifs) ;
- toutes les **annonces** vues, avec score, analyse, et votre avis (❤️ / 👎 + raison) ;
- les **concessions** de votre secteur (trouvées par l'agent ou ajoutées par vous), suivies ou écartées ;
- la **mémoire du chef** : ce que vous lui dites, ce que vous rejetez et pourquoi, les faits utiles
  appris pendant les missions (visible et effaçable dans *Profil*) ;
- l'historique des **missions** (le journal de chaque agent est consultable dans *Équipe*) et du **chat**.

### Comment les recherches continuent sans vous

L'iPhone ne laisse pas une app tourner en arrière-plan aussi longtemps qu'il le faudrait. Le travail
se fait donc sur un **petit serveur** (votre Mac, ou un serveur en ligne) qui :
1. relance une mission complète à la fréquence choisie (par défaut une fois par jour) ;
2. enregistre les nouvelles annonces et les note ;
3. vous envoie une **notification** (Web Push sur iPhone/Mac, et/ou [ntfy](https://ntfy.sh)) si une
   annonce dépasse votre seuil de score.

L'app sur l'iPhone et sur le Mac n'est qu'une fenêtre sur ce serveur : vos infos sont les mêmes partout.

---

## Installation

Il vous faut une **clé API Anthropic** ([console.anthropic.com](https://console.anthropic.com/) →
*API Keys*). L'utilisation est facturée à l'usage par Anthropic.

### Option A : sur votre Mac (le plus simple)

```bash
cd voiture
./scripts/installer_mac.sh        # 1er passage : crée .env → mettez-y votre clé
./scripts/installer_mac.sh        # 2e passage : installe et lance le serveur au démarrage du Mac
```

Ouvrez <http://127.0.0.1:8000> dans Safari. Le mot de passe de l'app est celui de `VOITURE_APP_TOKEN`
dans `.env` ; si vous l'avez laissé vide, il est généré et affiché dans `data/serveur.log`.

**Sur le Mac**, installez l'app : Safari → menu *Fichier* → **Ajouter au Dock** (macOS Sonoma ou plus récent).

> Limite : quand le Mac est éteint ou en veille, les recherches s'arrêtent (elles reprennent au réveil).
> Pour éviter la veille : *Réglages Système → Batterie/Énergie → Empêcher la suspension automatique*.

#### Accès depuis l'iPhone (Tailscale, gratuit)

Les notifications et l'installation sur iPhone exigent une adresse **HTTPS**. Le plus simple et le
plus sûr (rien n'est exposé sur Internet) :

1. Installez [Tailscale](https://tailscale.com/download) sur le Mac **et** l'iPhone, même compte.
2. Dans la console Tailscale, activez *MagicDNS* et *HTTPS Certificates* (page *DNS*).
3. Sur le Mac : `tailscale serve --bg 8000`. La commande affiche une adresse du type
   `https://mon-mac.nom-du-reseau.ts.net`.
4. Ouvrez cette adresse dans **Safari** sur l'iPhone (Tailscale activé).

### Option B : sur un serveur en ligne (recherches 24 h/24)

Le dossier contient un `Dockerfile` et un `docker-compose.yml` :

```bash
cd voiture
cp .env.example .env              # mettez votre clé et un mot de passe
docker compose up -d --build      # données dans ./data
```

Mettez-le derrière HTTPS (Caddy, Traefik…) ou utilisez un hébergeur qui le fournit. Exemple
**Fly.io** (fichier `fly.toml` fourni ; vérifiez les tarifs actuels de l'hébergeur) :

```bash
fly launch --no-deploy --copy-config
fly volumes create voiture_data --size 1
fly secrets set ANTHROPIC_API_KEY=sk-ant-... VOITURE_APP_TOKEN=un-mot-de-passe-long VOITURE_VAPID_CONTACT=mailto:vous@exemple.fr
fly deploy
```

### Installer l'app sur l'iPhone

1. Ouvrez l'adresse HTTPS de votre serveur dans **Safari**.
2. Touchez **Partager** → **Sur l'écran d'accueil** → *Ajouter*.
3. Ouvrez l'app **depuis l'icône**, connectez-vous, puis touchez **Activer les notifications** sur l'accueil
   (iOS 16.4 minimum ; les notifications web ne fonctionnent que pour une app ajoutée à l'écran d'accueil).
4. Dans *Profil → Tester les notifications* pour vérifier.

Alternative ou complément : installez l'app **ntfy** (App Store), abonnez-vous à un sujet difficile à
deviner (ex. `voiture-elias-7f3k`) et saisissez ce même sujet dans *Profil → Sujet ntfy*.

## Utilisation

1. **Profil** : remplissez ce que vous savez (même partiellement), ou discutez avec le **Chef** :
   il pose les questions une par une et remplit le profil tout seul.
2. **Accueil → Chercher maintenant** pour une première mission (quelques minutes). Les suivantes se
   lancent toutes seules.
3. **Annonces** : ❤️ pour garder, 👎 pour écarter **en disant pourquoi** : le chef s'en souvient aux
   missions suivantes. *Analyse de l'équipe* détaille juste prix, coût annuel, risque et conseil.
4. **Annonces → 🏢 Concessions** : touchez **Trouver les concessions** (votre ville doit être dans le
   profil), ou demandez au chef dans le chat : *« Trouve les concessions Toyota autour de chez moi »*,
   *« Ajoute le garage Martin à Caluire »*, *« Écarte la concession X, trop chère »*. Vous pouvez aussi
   en ajouter une à la main. Pour chacune : **Appeler**, **Stock**, **Site**, **Itinéraire** (Plans),
   ☆ **Suivre** ou 👎 **Écarter** (avec la raison, mémorisée). Le chasseur d'annonces fouille ensuite
   le stock des concessions suivies à chaque mission.
5. **Équipe** : le journal de chaque mission (ce que chaque agent a fait et rendu) et les jetons consommés.

## Coûts et limites (à lire)

- Chaque mission fait travailler plusieurs agents avec recherche web : comptez probablement de
  l'ordre d'**un à quelques dollars par mission** (estimation non mesurée, elle dépend du nombre de
  recherches). Regardez le compteur de jetons dans *Équipe* après la première mission et ajustez la
  **fréquence** et les **agents actifs** dans *Profil*. Garde-fous : `VOITURE_MAX_AGENT_CALLS`
  (10 consultations par mission par défaut) et `VOITURE_MAX_CHEF_TURNS`.
- Les modèles se règlent avec `VOITURE_CHEF_MODEL` et `VOITURE_AGENT_MODEL` (par défaut
  `claude-opus-5-5`). Si un modèle refuse une requête, l'API bascule automatiquement sur un modèle
  de secours (`fallbacks: "default"`) ; désactivable avec `VOITURE_FALLBACKS=0`.
- Les agents passent par la **recherche web d'Anthropic** : ils ne voient que ce que les moteurs ont
  indexé, avec un peu de retard, et certains sites bloquent la lecture de leurs pages. Ce n'est pas
  un scraper : aucune annonce ne garantit d'être encore en ligne. **Vérifiez toujours l'annonce** avant
  de vous déplacer, et ne payez jamais à distance.
- Les scores et estimations sont des avis d'IA, pas une expertise : faites inspecter le véhicule.

## Développement

```bash
cd voiture
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
VOITURE_NO_AUTOAPP=1 .venv/bin/python -m unittest discover -s tests -v   # tests sans réseau ni clé
.venv/bin/uvicorn app.main:app --reload                                   # http://127.0.0.1:8000
```

| Fichier | Contenu |
|---|---|
| `app/agents.py` | Définition des 7 agents (rôle, consignes, schéma du rapport, effort, outils web) |
| `app/llm.py` | Boucle d'un agent : recherche web, reprise après `pause_turn`, rapport via l'outil `rapporter` |
| `app/orchestrator.py` | Le chef : missions (agents en parallèle, budget d'appels), chat, mémoire |
| `app/db.py` | Mémoire SQLite (profil, réglages, annonces dédoublonnées, missions, chat, abonnements) |
| `app/scheduler.py` | Relance automatique des missions |
| `app/notify.py` | Web Push (clés VAPID générées automatiquement) et ntfy |
| `app/main.py` | API FastAPI protégée par mot de passe + service de l'app |
| `app/static/` | L'app installable (HTML/CSS/JS sans build, service worker, manifeste, icônes) |
