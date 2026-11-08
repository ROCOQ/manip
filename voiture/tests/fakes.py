"""Faux client Claude pour tester sans réseau ni clé API."""
from __future__ import annotations

import itertools
import threading
from types import SimpleNamespace

_ids = itertools.count(1)


def text(t: str):
    return SimpleNamespace(type="text", text=t)


def tool_use(name: str, payload: dict):
    return SimpleNamespace(type="tool_use", id=f"toolu_{next(_ids)}", name=name, input=payload)


def response(content, stop_reason="end_turn", tokens=(100, 50)):
    usage = SimpleNamespace(input_tokens=tokens[0], output_tokens=tokens[1],
                            cache_read_input_tokens=0, cache_creation_input_tokens=0)
    return SimpleNamespace(content=content, stop_reason=stop_reason, usage=usage)


class FakeMessages:
    def __init__(self, router):
        self.router = router
        self.calls: list[dict] = []
        self._lock = threading.Lock()

    def create(self, **kwargs):
        snapshot = {**kwargs, "messages": list(kwargs.get("messages", []))}
        with self._lock:
            self.calls.append(snapshot)
        return self.router(kwargs)


class FakeClient:
    """`router(kwargs) -> response` décide de la réponse selon le prompt système / l'historique."""

    def __init__(self, router):
        self.messages_api = FakeMessages(router)
        self.beta = SimpleNamespace(messages=self.messages_api)

    @property
    def calls(self):
        return self.messages_api.calls


LISTING_A = {
    "url": "https://www.lacentrale.fr/auto-occasion-annonce-1.html?utm_source=x",
    "titre": "Toyota Yaris Hybride 2021", "prix": "15 900 €", "km": 42000, "annee": 2021,
    "energie": "hybride", "boite": "automatique", "localisation": "Lyon", "vendeur": "particulier",
}
LISTING_B = {
    "url": "https://www.leboncoin.fr/ad/voitures/2.htm",
    "titre": "Renault Clio 5 E-Tech 2022", "prix": 16500, "km": 30000, "annee": 2022,
}

SPECIALIST_REPORTS = {
    "Conseiller besoins": {"synthese": "Citadine hybride conseillée.",
                           "modeles_recommandes": [{"modele": "Toyota Yaris", "pourquoi": "fiable"}]},
    "Chasseur d'annonces": {"synthese": "2 annonces.", "annonces": [LISTING_A, LISTING_B, {"url": "pas-une-url"}]},
    "Analyste prix": {"synthese": "Yaris bien placée.", "evaluations": [{"url": LISTING_A["url"], "verdict_prix": "bonne affaire"}]},
    "Détective anti-arnaque": {"synthese": "RAS.", "controles": [{"url": LISTING_A["url"], "risque": "faible"}]},
    "Expert fiabilité": {"synthese": "Très fiable.", "modeles": []},
    "Comptable auto": {"synthese": "1 800 €/an.", "estimations": []},
}


def specialist_name(system: str) -> str | None:
    for name in SPECIALIST_REPORTS:
        if f"« {name} »" in system:
            return name
    return None


def mission_router(kwargs):
    """Simule une mission complète : profil → annonces → prix+verif en parallèle → rapport."""
    system = kwargs["system"]
    name = specialist_name(system)
    if name:
        return response([tool_use("rapporter", SPECIALIST_REPORTS[name])], "tool_use")
    if "Tu es le chef d'une équipe" in system:
        n_assistant = sum(1 for m in kwargs["messages"] if m["role"] == "assistant")
        if n_assistant == 0:
            return response([text("Je commence."), tool_use("consulter_agent", {"agent": "profil", "consigne": "Cible ?"})], "tool_use")
        if n_assistant == 1:
            return response([tool_use("consulter_agent", {"agent": "annonces", "consigne": "Cherche des Yaris"})], "tool_use")
        if n_assistant == 2:
            return response([
                tool_use("consulter_agent", {"agent": "prix", "consigne": "Évalue"}),
                tool_use("consulter_agent", {"agent": "verif", "consigne": "Vérifie", "annonces_urls": [LISTING_A["url"]]}),
            ], "tool_use")
        return response([tool_use("publier_rapport", {
            "resume": "La Yaris est la meilleure piste.",
            "classement": [
                {"url": LISTING_A["url"], "score": 88, "verdict": "À appeler vite", "conseil": "Négocier à 15 200 €"},
                {"url": LISTING_B["url"], "score": 140, "verdict": "Correct"},
            ],
            "a_retenir": ["La Yaris 4 hybride est très fiable."],
            "notifier": True, "message_notification": "Une Yaris à saisir !",
        })], "tool_use")
    raise AssertionError(f"prompt inattendu : {system[:80]}")
