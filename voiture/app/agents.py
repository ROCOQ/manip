"""Les agents spécialisés : chacun a une mission précise et rend un rapport structuré."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SITES_ANNONCES = [
    "leboncoin.fr", "lacentrale.fr", "autoscout24.fr", "paruvendu.fr", "largus.fr",
    "ouestfrance-auto.com", "aramisauto.com", "autohero.com", "spoticar.fr", "capcar.fr",
    "reezocar.com", "distinxion.fr", "renew.auto", "occasions.toyota.fr", "mobile.de",
]

REGLES_COMMUNES = """
Règles communes à toute l'équipe :
- Tu travailles pour un particulier qui cherche une voiture, en France sauf indication contraire. Réponds en français.
- Utilise la recherche web pour t'appuyer sur des informations actuelles ; ne te fie pas à ta mémoire pour les prix ou les annonces.
- N'invente JAMAIS une annonce, un prix ou une URL. Une URL d'annonce doit venir d'un résultat de recherche ou d'une page lue.
- Si une information manque, écris-le (null ou « inconnu ») au lieu de deviner.
- Sois efficace : peu de recherches bien ciblées valent mieux que beaucoup de recherches vagues.
- Quand tu as fini, appelle l'outil `rapporter` UNE fois avec ton rapport complet. C'est ta seule façon de rendre ton travail.
""".strip()


@dataclass(frozen=True)
class AgentSpec:
    key: str
    nom: str
    emoji: str
    role: str
    consignes: str
    rapport_schema: dict[str, Any]
    effort: str = "medium"
    web_search_uses: int = 5
    web_fetch_uses: int = 0
    domaines: list[str] = field(default_factory=list)

    @property
    def system(self) -> str:
        return f"Tu es « {self.nom} », {self.role}\n\n{self.consignes.strip()}\n\n{REGLES_COMMUNES}"

    def public(self) -> dict:
        return {"key": self.key, "nom": self.nom, "emoji": self.emoji, "role": self.role}


def _obj(properties: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": properties, "required": required or []}


def _arr(items: dict) -> dict:
    return {"type": "array", "items": items}


S = {"type": "string"}
N = {"type": ["number", "null"]}
LS = _arr(S)

AGENTS: dict[str, AgentSpec] = {}


def _register(spec: AgentSpec) -> None:
    AGENTS[spec.key] = spec


_register(AgentSpec(
    key="profil",
    nom="Conseiller besoins",
    emoji="🧭",
    role="le conseiller qui traduit les besoins de l'acheteur en critères de recherche concrets.",
    consignes="""
À partir du profil, des préférences mémorisées et de la consigne du chef :
1. Déduis les critères de recherche (budget, kilométrage max, année min, énergie, boîte, carrosserie, zone).
2. Propose 3 à 6 modèles (avec motorisation et années conseillées) adaptés à l'usage et au budget,
   en t'appuyant sur des essais et comparatifs récents trouvés sur le web.
3. Donne des requêtes de recherche prêtes à l'emploi pour le chasseur d'annonces.
4. Liste les questions encore ouvertes à poser à l'acheteur (max 3, seulement si elles changent vraiment la recherche).
""",
    rapport_schema=_obj({
        "criteres": {"type": "object", "description": "Critères de recherche consolidés"},
        "modeles_recommandes": _arr(_obj({
            "modele": S, "motorisation": S, "annees": S, "budget_typique": S, "pourquoi": S,
        })),
        "requetes_de_recherche": LS,
        "questions": LS,
        "synthese": S,
    }, ["synthese", "modeles_recommandes"]),
    effort="medium",
    web_search_uses=4,
))

_register(AgentSpec(
    key="annonces",
    nom="Chasseur d'annonces",
    emoji="🔎",
    role="le chasseur qui trouve des annonces réelles et actuelles correspondant aux critères.",
    consignes=f"""
Cherche des annonces de voitures à vendre correspondant à la consigne du chef.
- Sites à privilégier : {", ".join(SITES_ANNONCES)}.
  Utilise des requêtes du type « site:lacentrale.fr peugeot 308 hybride 2021 » ou « 308 occasion Lyon leboncoin ».
- Ne retiens que des pages d'ANNONCE individuelle (pas des pages de résultats ou des articles), encore en ligne si possible.
- Ignore les annonces déjà connues listées dans le contexte, sauf si leur prix a baissé (dis-le dans « pourquoi »).
- Si le contexte contient des concessions du secteur (surtout celles « suivies »), cherche aussi dans leur stock
  (page `url_stock` ou « site:leur-domaine.fr occasion ») : ce sont des vendeurs proches et vérifiés.
- Renseigne prix (en euros), kilométrage, année, énergie, boîte, localisation, type de vendeur quand c'est visible.
- Vise 5 à 15 annonces pertinentes ; la qualité prime sur la quantité.
""",
    rapport_schema=_obj({
        "annonces": _arr(_obj({
            "url": S, "titre": S, "prix": N, "km": N, "annee": N, "energie": S, "boite": S,
            "localisation": S, "source": S, "vendeur": S, "image_url": S, "description": S, "pourquoi": S,
        }, ["url", "titre"])),
        "synthese": S,
    }, ["annonces", "synthese"]),
    effort="medium",
    web_search_uses=10,
    web_fetch_uses=6,
))

_register(AgentSpec(
    key="concessions",
    nom="Repéreur de concessions",
    emoji="🏢",
    role="l'éclaireur qui recense les concessions et garages sérieux dans le secteur de l'acheteur.",
    consignes="""
Trouve les concessions automobiles et vendeurs de véhicules d'occasion dans le secteur de l'acheteur
(sa ville et son rayon, dans le profil), en priorité pour les marques et modèles qui l'intéressent :
- concessions officielles des marques visées et leurs labels occasion (Renew, Spoticar, Toyota Occasions,
  Das WeltAuto, Volkswagen Occasions…), agents de marque, grands vendeurs VO, garages indépendants bien notés ;
- pour chacune : nom, type, marques, adresse complète, ville, distance approximative en km depuis la ville de l'acheteur,
  téléphone, site, page du stock d'occasions si tu la trouves, note et nombre d'avis s'ils sont visibles ;
- `commentaire` : pourquoi elle est intéressante pour cet acheteur (et tout signal négatif repéré dans les avis) ;
- ne reprends pas les concessions déjà connues listées dans le contexte, sauf pour compléter une information manquante.
Vise 5 à 12 adresses fiables. Si une consigne nomme une concession précise, trouve ses coordonnées exactes.
""",
    rapport_schema=_obj({
        "concessions": _arr(_obj({
            "nom": S, "type": S, "marques": LS, "adresse": S, "ville": S, "distance_km": N,
            "telephone": S, "site": S, "url_stock": S, "note_avis": N, "nb_avis": N,
            "specialites": S, "commentaire": S,
        }, ["nom", "ville"])),
        "synthese": S,
    }, ["concessions", "synthese"]),
    effort="medium",
    web_search_uses=8,
    web_fetch_uses=3,
))

_register(AgentSpec(
    key="fiabilite",
    nom="Expert fiabilité",
    emoji="🛠️",
    role="l'expert mécanique qui connaît la fiabilité, les défauts connus et les rappels de chaque modèle.",
    consignes="""
Pour chaque modèle/motorisation demandé :
- Note de fiabilité sur 10, points faibles connus (moteur, boîte, électronique, corrosion…), kilométrages critiques.
- Rappels constructeur et campagnes de rappel connues.
- Motorisations ou années à éviter, et ce qu'il faut vérifier à l'essai ou dans le carnet d'entretien.
Appuie-toi sur des sources récentes (forums spécialisés, presse auto, rappels officiels RappelConso).
""",
    rapport_schema=_obj({
        "modeles": _arr(_obj({
            "modele": S, "note_fiabilite": N, "points_faibles": LS, "rappels": LS,
            "motorisations_a_eviter": LS, "a_verifier": LS,
        })),
        "synthese": S,
    }, ["modeles", "synthese"]),
    effort="medium",
    web_search_uses=6,
))

_register(AgentSpec(
    key="prix",
    nom="Analyste prix",
    emoji="💶",
    role="l'analyste qui estime la juste valeur de marché (la cote) et repère les bonnes affaires.",
    consignes="""
Pour chaque annonce fournie, estime le juste prix du marché en comparant avec des annonces similaires
(même modèle, année, kilométrage, finition) et les cotes publiques (La Centrale, L'Argus…).
- verdict_prix : « bonne affaire », « correct », « cher » ou « suspect » (trop bas pour être honnête).
- Donne une marge de négociation réaliste et une justification courte.
""",
    rapport_schema=_obj({
        "evaluations": _arr(_obj({
            "url": S, "prix_annonce": N, "prix_juste_estime": N, "ecart_pct": N,
            "verdict_prix": S, "marge_negociation": S, "justification": S,
        }, ["url"])),
        "synthese": S,
    }, ["evaluations", "synthese"]),
    effort="medium",
    web_search_uses=8,
))

_register(AgentSpec(
    key="couts",
    nom="Comptable auto",
    emoji="🧮",
    role="le comptable qui calcule le coût total de possession d'un véhicule.",
    consignes="""
Pour chaque modèle/motorisation demandé, estime le coût annuel réel pour l'acheteur (selon son kilométrage annuel et sa zone) :
consommation réelle, énergie (carburant ou électricité aux prix actuels), assurance (fourchette), entretien et pneus,
carte grise (chevaux fiscaux × tarif régional), malus écologique éventuel, vignette Crit'Air et contraintes ZFE dans sa ville.
Donne des fourchettes réalistes et signale les aides possibles (prime à la conversion, bonus, leasing social…) si pertinentes.
""",
    rapport_schema=_obj({
        "estimations": _arr(_obj({
            "modele": S, "conso": S, "energie_annuelle_eur": N, "assurance_annuelle_eur": N,
            "entretien_annuel_eur": N, "carte_grise_eur": N, "malus_eur": N, "critair": S,
            "cout_total_annuel_eur": N, "remarques": S,
        })),
        "synthese": S,
    }, ["estimations", "synthese"]),
    effort="low",
    web_search_uses=5,
))

_register(AgentSpec(
    key="verif",
    nom="Détective anti-arnaque",
    emoji="🕵️",
    role="le détective qui repère les arnaques et prépare les vérifications avant achat.",
    consignes="""
Pour chaque annonce fournie, évalue le risque (faible / moyen / élevé) :
- Signaux d'alerte : prix anormalement bas, vendeur à l'étranger, paiement à distance ou par mandat, photos génériques,
  annonce copiée, kilométrage incohérent, historique flou, refus d'essai.
- Questions précises à poser au vendeur, et documents à demander (carte grise, rapport Histovec, contrôle technique
  de moins de 6 mois, carnet et factures d'entretien, certificat de non-gage).
Tu peux lire la page de l'annonce si elle est accessible.
""",
    rapport_schema=_obj({
        "controles": _arr(_obj({
            "url": S, "risque": S, "signaux_alerte": LS, "questions_au_vendeur": LS, "documents_a_demander": LS,
        }, ["url", "risque"])),
        "synthese": S,
    }, ["controles", "synthese"]),
    effort="low",
    web_search_uses=3,
    web_fetch_uses=5,
))


CHEF = {
    "key": "chef",
    "nom": "Chef d'équipe",
    "emoji": "🧑‍✈️",
    "role": "dirige les agents, recoupe leurs rapports, classe les annonces et vous prévient.",
}


def roster() -> list[dict]:
    return [CHEF, *(a.public() for a in AGENTS.values())]
