"""Serveur web : API + app installable (PWA) pour iPhone et Mac."""
from __future__ import annotations

import asyncio
import contextlib
import hmac
import logging
import os
import secrets
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config
from .agents import roster
from .db import DEALER_STATUSES, LISTING_STATUSES, Store
from .notify import ensure_vapid, make_notifier, send_ntfy, send_webpush
from .orchestrator import Chef
from .scheduler import next_run_at, scheduler_loop

log = logging.getLogger("voiture")
STATIC = Path(__file__).resolve().parent / "static"


class ChatIn(BaseModel):
    message: str


class MissionIn(BaseModel):
    consigne: str = ""


class StatusIn(BaseModel):
    statut: str
    feedback: str | None = None


class NoteIn(BaseModel):
    note: str


class DealerIn(BaseModel):
    nom: str
    ville: str
    type: str | None = None
    marques: list[str] = []
    adresse: str | None = None
    telephone: str | None = None
    site: str | None = None
    url_stock: str | None = None
    commentaire: str | None = None


class DealerStatusIn(BaseModel):
    statut: str
    notes: str | None = None


class DealerSearchIn(BaseModel):
    consigne: str = ""


def resolve_token(store: Store) -> str:
    if config.APP_TOKEN:
        return config.APP_TOKEN
    token = store.get_kv("app_token")
    if not token:
        token = secrets.token_urlsafe(12)
        store.set_kv("app_token", token)
        log.warning("Aucun VOITURE_APP_TOKEN défini : mot de passe de l'app généré = %s", token)
    return token


def create_app(store: Store | None = None, chef: Chef | None = None, scheduler: bool | None = None) -> FastAPI:
    store = store or Store(config.DB_PATH)
    store.fail_stale_runs()
    public_url = os.environ.get("VOITURE_PUBLIC_URL")
    chef = chef or Chef(store, notifier=make_notifier(store, public_url))
    if chef.notifier is None:
        chef.notifier = make_notifier(store, public_url)
    token = resolve_token(store)
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        log.warning("ANTHROPIC_API_KEY n'est pas défini : les agents ne pourront pas travailler.")
    run_scheduler = config.SCHEDULER_ENABLED if scheduler is None else scheduler

    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI):
        task = asyncio.create_task(scheduler_loop(store, chef)) if run_scheduler else None
        yield
        if task:
            task.cancel()

    app = FastAPI(title="Chasseur de voiture", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.store, app.state.chef = store, chef

    def auth(request: Request) -> None:
        header = request.headers.get("authorization", "")
        given = header[7:] if header.lower().startswith("bearer ") else request.headers.get("x-app-token", "")
        if not given or not hmac.compare_digest(given.encode(), token.encode()):
            raise HTTPException(status_code=401, detail="Mot de passe de l'app invalide")

    api = [Depends(auth)]

    # ---------------------------------------------------------------- pages
    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/sw.js", include_in_schema=False)
    def service_worker():
        return FileResponse(STATIC / "sw.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})

    @app.get("/manifest.webmanifest", include_in_schema=False)
    def manifest():
        return FileResponse(STATIC / "manifest.webmanifest", media_type="application/manifest+json")

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        return {"ok": True}

    # ---------------------------------------------------------------- état
    @app.get("/api/status", dependencies=api)
    def status():
        settings = store.get_settings()
        nxt = next_run_at(settings, store.last_run_start())
        last = store.last_finished_run()
        return {
            "mission_en_cours": chef.current_run_id,
            "chat_occupe": chef.chat_busy,
            "recherche_concessions": chef.dealer_search_busy(),
            "prochaine_mission": nxt.isoformat(timespec="minutes") if nxt else None,
            "profil_vide": store.profile_is_empty(),
            "dernier_rapport": last["rapport"] if last else None,
            "derniere_mission": {k: last[k] for k in ("id", "debut", "fin")} if last else None,
            "nb_annonces": len(store.list_listings()),
            "nb_appareils_notifies": len(store.push_subscriptions()),
        }

    @app.get("/api/agents", dependencies=api)
    def agents():
        return roster()

    # ---------------------------------------------------------------- profil & réglages
    @app.get("/api/profile", dependencies=api)
    def get_profile():
        return store.get_profile()

    @app.put("/api/profile", dependencies=api)
    def put_profile(patch: dict[str, Any]):
        return store.update_profile(patch)

    @app.get("/api/settings", dependencies=api)
    def get_settings():
        return store.get_settings()

    @app.put("/api/settings", dependencies=api)
    def put_settings(patch: dict[str, Any]):
        try:
            return store.update_settings(patch)
        except (TypeError, ValueError) as exc:
            raise HTTPException(400, f"Réglages invalides : {exc}") from exc

    # ---------------------------------------------------------------- missions
    @app.post("/api/missions", dependencies=api)
    def start_mission(body: MissionIn):
        run_id = chef.start_mission_async("manuel", body.consigne)
        if run_id is None:
            raise HTTPException(409, "Une mission est déjà en cours.")
        return {"id": run_id}

    @app.get("/api/missions", dependencies=api)
    def list_missions():
        return [
            {k: r[k] for k in ("id", "declencheur", "statut", "debut", "fin", "erreur", "tokens_entree", "tokens_sortie")}
            | {"resume": (r["rapport"] or {}).get("resume"), "etapes": len(r["journal"])}
            for r in store.list_runs(30)
        ]

    @app.get("/api/missions/{run_id}", dependencies=api)
    def get_mission(run_id: int):
        run = store.get_run(run_id)
        if not run:
            raise HTTPException(404, "Mission introuvable")
        return run

    # ---------------------------------------------------------------- annonces
    @app.get("/api/listings", dependencies=api)
    def listings(statut: str | None = None):
        if statut and statut not in LISTING_STATUSES:
            raise HTTPException(400, "Statut inconnu")
        return store.list_listings(statut)

    @app.post("/api/listings/{listing_id}/status", dependencies=api)
    def listing_status(listing_id: int, body: StatusIn):
        try:
            listing = store.set_listing_status(listing_id, body.statut, body.feedback)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        if not listing:
            raise HTTPException(404, "Annonce introuvable")
        return listing

    # ---------------------------------------------------------------- concessions
    @app.get("/api/dealers", dependencies=api)
    def dealers(statut: str | None = None):
        if statut and statut not in DEALER_STATUSES:
            raise HTTPException(400, "Statut inconnu")
        return {
            "concessions": store.list_dealers(statut),
            "recherche_en_cours": chef.dealer_search_busy(),
            "derniere_recherche": store.get_kv("derniere_recherche_concessions"),
        }

    @app.post("/api/dealers", dependencies=api)
    def add_dealer(body: DealerIn):
        if not body.nom.strip() or not body.ville.strip():
            raise HTTPException(400, "Nom et ville obligatoires")
        saved = store.upsert_dealer(body.model_dump(), origine="utilisateur")
        if saved is None:
            raise HTTPException(400, "Concession invalide")
        return store.set_dealer_status(saved[0], "suivie")

    @app.post("/api/dealers/search", dependencies=api)
    def search_dealers(body: DealerSearchIn):
        if not store.get_profile().get("localisation") and not body.consigne.strip():
            raise HTTPException(400, "Indiquez d'abord votre ville dans le profil.")
        if not chef.search_dealers_async(body.consigne[:1000]):
            raise HTTPException(409, "Une recherche de concessions est déjà en cours.")
        return {"ok": True}

    @app.post("/api/dealers/{dealer_id}/status", dependencies=api)
    def dealer_status(dealer_id: int, body: DealerStatusIn):
        try:
            dealer = store.set_dealer_status(dealer_id, body.statut, body.notes)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        if not dealer:
            raise HTTPException(404, "Concession introuvable")
        return dealer

    @app.delete("/api/dealers/{dealer_id}", dependencies=api)
    def delete_dealer(dealer_id: int):
        if not store.delete_dealer(dealer_id):
            raise HTTPException(404, "Concession introuvable")
        return {"ok": True}

    # ---------------------------------------------------------------- chat
    @app.get("/api/chat", dependencies=api)
    def chat_history():
        return {"messages": store.chat_history(100), "occupe": chef.chat_busy}

    @app.post("/api/chat", dependencies=api)
    def chat(body: ChatIn):
        message = body.message.strip()
        if not message:
            raise HTTPException(400, "Message vide")
        if not chef.chat_async(message[:4000]):
            raise HTTPException(409, "Le chef répond déjà à un message.")
        return {"ok": True}

    @app.delete("/api/chat", dependencies=api)
    def clear_chat():
        store.clear_chat()
        return {"ok": True}

    # ---------------------------------------------------------------- mémoire
    @app.get("/api/memory", dependencies=api)
    def memory():
        return store.memories(200)

    @app.post("/api/memory", dependencies=api)
    def add_memory(body: NoteIn):
        store.add_memory(body.note)
        return {"ok": True}

    @app.delete("/api/memory/{memory_id}", dependencies=api)
    def delete_memory(memory_id: int):
        store.delete_memory(memory_id)
        return {"ok": True}

    # ---------------------------------------------------------------- notifications
    @app.get("/api/push/vapid", dependencies=api)
    def vapid_key():
        return {"publicKey": ensure_vapid(store)["public_key"]}

    @app.post("/api/push/subscribe", dependencies=api)
    def subscribe(subscription: dict[str, Any]):
        try:
            store.add_push_subscription(subscription)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"ok": True}

    @app.post("/api/push/test", dependencies=api)
    def push_test():
        payload = {"title": "🚗 Test réussi", "body": "Les notifications du chasseur de voiture fonctionnent.", "url": "/"}
        sent = send_webpush(store, payload)
        ntfy = send_ntfy(store.get_settings().get("ntfy_topic", ""), payload["title"], payload["body"])
        return {"web_push": sent, "ntfy": ntfy}

    @app.exception_handler(Exception)
    async def unexpected(_request: Request, exc: Exception):
        log.exception("erreur inattendue")
        return JSONResponse({"detail": f"Erreur interne : {type(exc).__name__}"}, status_code=500)

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


def _default_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    return create_app()


if os.environ.get("VOITURE_NO_AUTOAPP") != "1":
    app = _default_app()
