"""Le chef d'équipe : il dirige les agents, recoupe leurs rapports et tient la mémoire à jour."""
from __future__ import annotations

import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any, Callable

from . import config
from .agents import AGENTS
from .db import Store, normalize_url
from .llm import AgentError, create_message, run_specialist, text_of, usage_tokens

log = logging.getLogger("voiture.chef")

PUBLISH_TOOL = "publier_rapport"
CONSULT_TOOL = "consulter_agent"
MAX_RESULT_CHARS = 14000

CHEF_SYSTEM = """
Tu es le chef d'une équipe d'agents IA qui aide un particulier à trouver SA voiture.
Tu ne cherches pas toi-même sur le web : tu donnes des consignes précises à tes agents avec l'outil `consulter_agent`,
tu recoupes leurs rapports, puis tu publies une synthèse avec `publier_rapport`.

Ton équipe :
{equipe}

Déroulé conseillé d'une mission :
1. Si le profil a changé ou si aucune liste de modèles n'existe encore, consulte d'abord le conseiller besoins.
2. Si aucune concession du secteur n'est connue (`concessions_connues` vide) et que le repéreur est dans l'équipe,
   envoie-le une fois en parallèle du chasseur. Ensuite, demande au chasseur de fouiller aussi le stock des concessions suivies.
   Envoie le chasseur d'annonces avec des critères et des modèles précis (tu peux l'envoyer plusieurs fois, sur des modèles différents).
3. En parallèle (plusieurs appels dans le même message), fais évaluer les annonces trouvées par l'analyste prix et le détective,
   et les modèles par l'expert fiabilité et le comptable (inutile de refaire fiabilité/coûts si la mémoire les contient déjà).
4. Publie le rapport : classe les annonces avec un score de 0 à 100 :
   90+ : excellente affaire qui coche tout ; 75-89 : très bonne piste à contacter vite ; 50-74 : correcte mais avec des compromis ;
   moins de 50 : à éviter (explique pourquoi). Un risque d'arnaque élevé plafonne le score à 30.
   Mets `notifier` à vrai seulement s'il y a du nouveau qui mérite que l'acheteur soit prévenu.

Règles :
- Respecte strictement le budget, les critères rédhibitoires et les préférences mémorisées (annonces rejetées, goûts exprimés).
- Ne reclasse pas les annonces déjà rejetées. Ne reprends une annonce déjà vue que si elle a changé.
- Tu as un budget de {max_appels} consultations d'agents par mission : sois économe.
- N'invente rien : seules les annonces rapportées par le chasseur existent.
- Écris en français, de façon claire et concrète, pour quelqu'un qui lira sur son téléphone.
""".strip()

CHAT_SYSTEM = """
Tu es le chef d'une équipe d'agents IA qui aide l'utilisateur à trouver sa voiture. Tu discutes avec lui dans l'app, sur téléphone.
- Apprends à le connaître : budget, usage, trajets, famille, goûts, contraintes. Pose UNE ou DEUX questions à la fois, pas plus.
- Dès que tu apprends quelque chose d'utile, enregistre-le : `mettre_a_jour_profil` pour les champs du profil,
  `memoriser` pour tout le reste (goûts, contraintes, avis sur des annonces). Ne demande pas la permission pour ça.
- Pour une question précise (fiabilité d'un modèle, coût, cote, annonce douteuse), consulte l'agent adapté avec `consulter_agent`.
- Concessions : pour trouver celles du secteur, consulte l'agent `concessions` (ce qu'il trouve est enregistré tout seul
  et s'affiche dans l'onglet Annonces → Concessions). Si l'utilisateur cite une concession ou un garage précis,
  ajoute-le avec `ajouter_concession` (suivie = oui), puis consulte le repéreur si des coordonnées manquent.
  Pour en écarter une, utilise `modifier_concession`.
- Quand le profil est assez complet ou si l'utilisateur le demande, lance une mission complète avec `lancer_mission`
  (elle tourne en arrière-plan ; les résultats arrivent dans l'onglet Annonces et en notification).
- Réponses courtes, concrètes, sans jargon. Pas de longs tableaux.

Ton équipe :
{equipe}
""".strip()


def _equipe() -> str:
    return "\n".join(f"- `{a.key}` — {a.emoji} {a.nom} : {a.role}" for a in AGENTS.values())


def _truncate(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text) > MAX_RESULT_CHARS:
        text = text[:MAX_RESULT_CHARS] + "… (tronqué)"
    return text


def consult_tool(agent_keys: list[str]) -> dict:
    return {
        "name": CONSULT_TOOL,
        "description": (
            "Confier une tâche à un agent spécialisé et recevoir son rapport. "
            "Plusieurs appels dans le même message s'exécutent en parallèle."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent": {"type": "string", "enum": agent_keys},
                "consigne": {"type": "string", "description": "Tâche précise : modèles, critères, ce que tu attends."},
                "annonces_urls": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Pour prix/verif : URLs des annonces à examiner (leurs détails sont joints automatiquement).",
                },
            },
            "required": ["agent", "consigne"],
        },
    }


PUBLISH_SCHEMA = {
    "name": PUBLISH_TOOL,
    "description": "Publier la synthèse finale de la mission et le classement des annonces. Termine la mission.",
    "input_schema": {
        "type": "object",
        "properties": {
            "resume": {"type": "string", "description": "Synthèse pour l'acheteur (5 à 10 lignes)."},
            "classement": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "score": {"type": "number"},
                        "verdict": {"type": "string", "description": "Une phrase."},
                        "points_forts": {"type": "array", "items": {"type": "string"}},
                        "points_faibles": {"type": "array", "items": {"type": "string"}},
                        "prix_juste_estime": {"type": ["number", "null"]},
                        "cout_annuel_estime": {"type": ["number", "null"]},
                        "risque": {"type": "string"},
                        "conseil": {"type": "string", "description": "Prochaine action : appeler, négocier à X €, demander Y…"},
                    },
                    "required": ["url", "score", "verdict"],
                },
            },
            "modeles_conseilles": {"type": "array", "items": {"type": "string"}},
            "a_retenir": {
                "type": "array", "items": {"type": "string"},
                "description": "Faits durables à mémoriser pour les prochaines missions (fiabilité, coûts, cotes…).",
            },
            "questions": {"type": "array", "items": {"type": "string"}, "description": "Questions à poser à l'acheteur."},
            "notifier": {"type": "boolean"},
            "message_notification": {"type": "string"},
        },
        "required": ["resume", "classement", "notifier"],
    },
}

PROFILE_TOOL = {
    "name": "mettre_a_jour_profil",
    "description": "Mettre à jour le profil de l'acheteur (seuls les champs fournis changent).",
    "input_schema": {
        "type": "object",
        "properties": {"modifications": {"type": "object", "description": "Champs du profil à modifier."}},
        "required": ["modifications"],
    },
}
MEMORY_TOOL = {
    "name": "memoriser",
    "description": "Mémoriser durablement une information utile sur l'acheteur ou sa recherche.",
    "input_schema": {"type": "object", "properties": {"note": {"type": "string"}}, "required": ["note"]},
}
DEALER_FIELDS = {
    "nom": {"type": "string"},
    "ville": {"type": "string"},
    "type": {"type": "string", "description": "concession officielle, agent, garage indépendant, vendeur VO…"},
    "marques": {"type": "array", "items": {"type": "string"}},
    "adresse": {"type": "string"},
    "telephone": {"type": "string"},
    "site": {"type": "string"},
    "url_stock": {"type": "string"},
    "commentaire": {"type": "string"},
}
ADD_DEALER_TOOL = {
    "name": "ajouter_concession",
    "description": "Ajouter une concession ou un garage à la liste suivie par l'utilisateur.",
    "input_schema": {
        "type": "object",
        "properties": {**DEALER_FIELDS, "suivre": {"type": "boolean", "description": "Vrai par défaut."}},
        "required": ["nom", "ville"],
    },
}
EDIT_DEALER_TOOL = {
    "name": "modifier_concession",
    "description": "Changer le statut d'une concession connue (par son id) : suivie, ignoree ou nouvelle, avec une note.",
    "input_schema": {
        "type": "object",
        "properties": {
            "id": {"type": "integer"},
            "statut": {"type": "string", "enum": ["suivie", "ignoree", "nouvelle"]},
            "note": {"type": "string"},
        },
        "required": ["id", "statut"],
    },
}

MISSION_TOOL = {
    "name": "lancer_mission",
    "description": "Lancer en arrière-plan une mission complète de recherche d'annonces.",
    "input_schema": {
        "type": "object",
        "properties": {"consigne": {"type": "string", "description": "Ce sur quoi la mission doit se concentrer."}},
        "required": [],
    },
}


class Chef:
    def __init__(self, store: Store, client=None, notifier: Callable[[dict], None] | None = None):
        self.store = store
        self._client = client
        self.notifier = notifier
        self._mission_lock = threading.Lock()
        self._chat_lock = threading.Lock()
        self._dealer_lock = threading.Lock()
        self.current_run_id: int | None = None
        self.chat_busy = False

    @property
    def client(self):
        if self._client is None:
            from .llm import make_client

            self._client = make_client()
        return self._client

    # ------------------------------------------------------------------ contexte
    def _active_agents(self) -> list[str]:
        actifs = self.store.get_settings().get("agents_actifs") or list(AGENTS)
        keys = [k for k in actifs if k in AGENTS]
        if "annonces" not in keys:
            keys.append("annonces")
        return keys

    def memory_context(self) -> dict:
        last = self.store.last_finished_run()
        return {
            "date_du_jour": date.today().isoformat(),
            "profil": self.store.get_profile(),
            "memoire": [m["note"] for m in self.store.memories(40)],
            "annonces_deja_connues": self.store.known_listings_digest(60),
            "concessions_connues": self.store.dealers_digest(30),
            "dernier_rapport": (last or {}).get("rapport", {}) and {
                "resume": last["rapport"].get("resume"),
                "modeles_conseilles": last["rapport"].get("modeles_conseilles"),
            },
        }

    def _agent_context(self, agent_key: str, urls: list[str] | None, run_listing_urls: list[str]) -> dict:
        ctx = {
            "date_du_jour": date.today().isoformat(),
            "profil": self.store.get_profile(),
            "memoire": [m["note"] for m in self.store.memories(30)],
        }
        if agent_key == "annonces":
            ctx["annonces_deja_connues"] = [
                {k: r[k] for k in ("url", "prix", "statut")} for r in self.store.known_listings_digest(80)
            ]
        if agent_key in ("annonces", "concessions"):
            ctx["concessions_connues"] = self.store.dealers_digest(40)
        if agent_key in ("prix", "verif"):
            wanted = {normalize_url(u) for u in (urls or run_listing_urls)}
            ctx["annonces"] = [
                {k: l.get(k) for k in ("url", "titre", "prix", "km", "annee", "energie", "boite",
                                       "localisation", "vendeur", "description")}
                for l in self.store.list_listings(limit=300) if l["url"] in wanted
            ][:20]
        return ctx

    # ------------------------------------------------------------------ agents
    def consult(self, agent_key: str, consigne: str, urls: list[str] | None = None,
                run_id: int | None = None, run_listing_urls: list[str] | None = None) -> dict:
        spec = AGENTS.get(agent_key)
        if spec is None:
            return {"erreur": f"agent inconnu : {agent_key}"}
        run_listing_urls = run_listing_urls if run_listing_urls is not None else []
        started = time.monotonic()

        def on_usage(tokens_in: int, tokens_out: int) -> None:
            if run_id:
                self.store.add_usage(run_id, tokens_in, tokens_out)

        try:
            report = run_specialist(
                self.client, spec, consigne,
                self._agent_context(agent_key, urls, run_listing_urls), on_usage,
            )
        except AgentError as exc:
            report = {"erreur": str(exc)}
        except Exception as exc:  # erreur réseau / API : le chef doit pouvoir continuer
            log.exception("agent %s en échec", agent_key)
            report = {"erreur": f"{spec.nom} indisponible : {type(exc).__name__}"}

        if agent_key == "annonces" and "annonces" in report:
            report = self._store_listings(report, run_id, run_listing_urls)
        if agent_key == "concessions" and "concessions" in report:
            report = self._store_dealers(report)

        if run_id:
            self.store.append_journal(run_id, {
                "agent": agent_key, "consigne": consigne,
                "duree_s": round(time.monotonic() - started, 1), "rapport": report,
            })
        return report

    def _store_listings(self, report: dict, run_id: int | None, run_listing_urls: list[str]) -> dict:
        annotated = []
        for item in report.get("annonces") or []:
            if not isinstance(item, dict):
                continue
            saved = self.store.upsert_listing(item, run_id)
            if saved is None:
                continue
            listing_id, is_new = saved
            url = normalize_url(item.get("url", ""))
            if url not in run_listing_urls:
                run_listing_urls.append(url)
            annotated.append({**item, "url": url, "id": listing_id, "nouvelle": is_new})
        return {**report, "annonces": annotated}

    def _store_dealers(self, report: dict) -> dict:
        annotated = []
        for item in report.get("concessions") or []:
            if not isinstance(item, dict):
                continue
            saved = self.store.upsert_dealer(item)
            if saved is None:
                continue
            dealer_id, is_new = saved
            annotated.append({**item, "id": dealer_id, "nouvelle": is_new})
        return {**report, "concessions": annotated}

    # ------------------------------------------------------------------ concessions
    def dealer_search_busy(self) -> bool:
        return self._dealer_lock.locked()

    def search_dealers_async(self, consigne: str = "") -> bool:
        """Lance le repéreur de concessions en arrière-plan (bouton de l'app). False s'il tourne déjà."""
        if not self._dealer_lock.acquire(blocking=False):
            return False
        consigne = consigne.strip() or (
            "Recense les concessions et garages sérieux de mon secteur pour les marques et modèles qui m'intéressent."
        )

        def worker() -> None:
            try:
                report = self.consult("concessions", consigne)
                self.store.set_kv("derniere_recherche_concessions", {
                    "synthese": report.get("synthese") or report.get("erreur"),
                    "erreur": bool(report.get("erreur")),
                    "nouvelles": sum(1 for c in report.get("concessions") or [] if c.get("nouvelle")),
                })
            finally:
                self._dealer_lock.release()

        threading.Thread(target=worker, name="concessions", daemon=True).start()
        return True

    def _run_tool_calls(self, blocks, handler: Callable[[Any], str]) -> list[dict]:
        """Exécute les appels d'outils en parallèle et renvoie tous les résultats dans l'ordre."""
        if not blocks:
            return []
        with ThreadPoolExecutor(max_workers=min(6, len(blocks))) as pool:
            outputs = list(pool.map(handler, blocks))
        return [
            {"type": "tool_result", "tool_use_id": b.id, "content": out}
            for b, out in zip(blocks, outputs)
        ]

    # ------------------------------------------------------------------ mission
    def is_running(self) -> bool:
        return self._mission_lock.locked()

    def start_mission_async(self, declencheur: str, consigne: str = "") -> int | None:
        """Lance une mission dans un thread. Renvoie l'id de mission, ou None si une mission tourne déjà."""
        if not self._mission_lock.acquire(blocking=False):
            return None
        run_id = self.store.start_run(declencheur)
        self.current_run_id = run_id

        def worker() -> None:
            try:
                self._mission(run_id, consigne)
            finally:
                self.current_run_id = None
                self._mission_lock.release()

        threading.Thread(target=worker, name=f"mission-{run_id}", daemon=True).start()
        return run_id

    def run_mission_blocking(self, declencheur: str, consigne: str = "") -> int | None:
        if not self._mission_lock.acquire(blocking=False):
            return None
        try:
            run_id = self.store.start_run(declencheur)
            self.current_run_id = run_id
            self._mission(run_id, consigne)
            return run_id
        finally:
            self.current_run_id = None
            self._mission_lock.release()

    def _mission(self, run_id: int, consigne: str) -> None:
        try:
            report = self._mission_loop(run_id, consigne)
            self._apply_report(report)
            self.store.finish_run(run_id, "terminee", rapport=report)
            if self.notifier:
                try:
                    self.notifier(report)
                except Exception:
                    log.exception("échec de l'envoi des notifications")
        except Exception as exc:
            log.exception("mission %s en échec", run_id)
            self.store.finish_run(run_id, "echec", erreur=f"{type(exc).__name__}: {exc}")

    def _mission_loop(self, run_id: int, consigne: str) -> dict:
        agent_keys = self._active_agents()
        tools = [consult_tool(agent_keys), PUBLISH_SCHEMA]
        system = CHEF_SYSTEM.format(equipe=_equipe(), max_appels=config.MAX_AGENT_CALLS)
        mission = consigne.strip() or "Mission planifiée : trouve les meilleures annonces du moment pour cet acheteur."
        messages: list[dict] = [{
            "role": "user",
            "content": "Mémoire et contexte (JSON) :\n"
                       + json.dumps(self.memory_context(), ensure_ascii=False, indent=1, default=str)
                       + f"\n\nMission : {mission}",
        }]
        run_listing_urls: list[str] = []
        calls = 0
        calls_lock = threading.Lock()

        def handle(block) -> str:
            nonlocal calls
            if block.name != CONSULT_TOOL:
                return json.dumps({"erreur": f"outil inconnu : {block.name}"})
            with calls_lock:
                calls += 1
                over = calls > config.MAX_AGENT_CALLS
            if over:
                return json.dumps({"erreur": "Budget de consultations épuisé : publie maintenant ton rapport."})
            args = block.input if isinstance(block.input, dict) else {}
            agent = args.get("agent", "")
            if agent not in agent_keys:
                return json.dumps({"erreur": f"agent indisponible : {agent}"})
            report = self.consult(agent, args.get("consigne", ""), args.get("annonces_urls"),
                                  run_id, run_listing_urls)
            return _truncate(report)

        for _ in range(config.MAX_CHEF_TURNS):
            response = create_message(
                self.client,
                model=config.CHEF_MODEL,
                max_tokens=16000,
                system=system,
                tools=tools,
                messages=messages,
                output_config={"effort": "high"},
                cache_control={"type": "ephemeral"},
            )
            self.store.add_usage(run_id, *usage_tokens(response))
            if response.stop_reason == "refusal":
                raise RuntimeError("le chef a refusé la mission")

            blocks = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
            for b in blocks:
                if b.name == PUBLISH_TOOL:
                    report = b.input if isinstance(b.input, dict) else {}
                    self.store.append_journal(run_id, {"agent": "chef", "consigne": "rapport final", "rapport": report})
                    return report

            messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason == "pause_turn":
                continue
            if not blocks:
                messages.append({"role": "user", "content": f"Publie maintenant ton rapport avec `{PUBLISH_TOOL}`."})
                continue
            messages.append({"role": "user", "content": self._run_tool_calls(blocks, handle)})

        return {
            "resume": "La mission s'est arrêtée avant la synthèse (limite de tours atteinte).",
            "classement": [], "notifier": False,
        }

    def _apply_report(self, report: dict) -> None:
        for item in report.get("classement") or []:
            if isinstance(item, dict) and item.get("url"):
                analyse = {k: v for k, v in item.items() if k not in ("url", "score", "verdict")}
                self.store.score_listing(item["url"], item.get("score"), item.get("verdict"), analyse)
        for fact in report.get("a_retenir") or []:
            if isinstance(fact, str):
                self.store.add_memory(fact)

    # ------------------------------------------------------------------ chat
    def chat_async(self, message: str) -> bool:
        if not self._chat_lock.acquire(blocking=False):
            return False
        self.chat_busy = True
        self.store.add_chat("user", message)

        def worker() -> None:
            try:
                answer = self._chat_reply()
            except Exception as exc:
                log.exception("chat en échec")
                answer = f"Désolé, je n'ai pas pu répondre ({type(exc).__name__}). Réessayez dans un instant."
            self.store.add_chat("assistant", answer or "…")
            self.chat_busy = False
            self._chat_lock.release()

        threading.Thread(target=worker, name="chat", daemon=True).start()
        return True

    def chat_blocking(self, message: str) -> str:
        with self._chat_lock:
            self.store.add_chat("user", message)
            answer = self._chat_reply()
            self.store.add_chat("assistant", answer)
            return answer

    def _chat_reply(self) -> str:
        agent_keys = list(AGENTS)
        tools = [consult_tool(agent_keys), PROFILE_TOOL, MEMORY_TOOL, ADD_DEALER_TOOL, EDIT_DEALER_TOOL, MISSION_TOOL]
        system = CHAT_SYSTEM.format(equipe=_equipe())
        history = self.store.chat_history(30)
        messages: list[dict] = [
            {"role": h["role"], "content": h["content"]} for h in history if h["role"] in ("user", "assistant")
        ]
        while messages and messages[0]["role"] != "user":
            messages.pop(0)
        # Le contexte mémoire (qui change à chaque tour) est ajouté après l'historique stable.
        messages.append({
            "role": "user",
            "content": "[Contexte à jour fourni par l'app, pas écrit par l'utilisateur]\n"
                       + json.dumps(self.memory_context(), ensure_ascii=False, default=str),
        })

        def handle(block) -> str:
            args = block.input if isinstance(block.input, dict) else {}
            if block.name == CONSULT_TOOL:
                return _truncate(self.consult(args.get("agent", ""), args.get("consigne", ""), args.get("annonces_urls")))
            if block.name == PROFILE_TOOL["name"]:
                profile = self.store.update_profile(args.get("modifications") or {})
                return _truncate({"ok": True, "profil": profile})
            if block.name == ADD_DEALER_TOOL["name"]:
                follow = args.pop("suivre", True)
                saved = self.store.upsert_dealer(args, origine="utilisateur" if follow else "agent")
                if saved is None:
                    return json.dumps({"ok": False, "erreur": "nom manquant"})
                if follow:
                    self.store.set_dealer_status(saved[0], "suivie")
                return _truncate({"ok": True, "concession": self.store.get_dealer(saved[0])})
            if block.name == EDIT_DEALER_TOOL["name"]:
                try:
                    dealer = self.store.set_dealer_status(int(args.get("id", 0)), args.get("statut", ""), args.get("note"))
                except (TypeError, ValueError) as exc:
                    return json.dumps({"ok": False, "erreur": str(exc)})
                return _truncate({"ok": dealer is not None, "concession": dealer})
            if block.name == MEMORY_TOOL["name"]:
                self.store.add_memory(args.get("note", ""))
                return json.dumps({"ok": True})
            if block.name == MISSION_TOOL["name"]:
                run_id = self.start_mission_async("chat", args.get("consigne", ""))
                if run_id is None:
                    return json.dumps({"ok": False, "info": "Une mission est déjà en cours."})
                return json.dumps({"ok": True, "mission": run_id})
            return json.dumps({"erreur": f"outil inconnu : {block.name}"})

        for _ in range(8):
            response = create_message(
                self.client,
                model=config.CHEF_MODEL,
                max_tokens=8000,
                system=system,
                tools=tools,
                messages=messages,
                output_config={"effort": "medium"},
                cache_control={"type": "ephemeral"},
            )
            if response.stop_reason == "refusal":
                return "Je ne peux pas répondre à cette demande."
            blocks = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
            if response.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": response.content})
                continue
            if not blocks:
                return text_of(response.content)
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": self._run_tool_calls(blocks, handle)})
        return "J'ai beaucoup travaillé sur cette question ; relancez-moi si besoin de plus de détails."
