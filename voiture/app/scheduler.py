"""Planificateur : relance les missions en arrière-plan, même quand l'app est fermée."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from . import config
from .db import Store
from .orchestrator import Chef

log = logging.getLogger("voiture.scheduler")


def next_run_at(settings: dict, last_start: str | None) -> datetime | None:
    if not settings.get("recherche_auto"):
        return None
    if not last_start:
        return datetime.now(timezone.utc)
    last = datetime.fromisoformat(last_start)
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return last + timedelta(hours=max(1, int(settings.get("frequence_heures") or 24)))


def should_run(store: Store, chef: Chef, now: datetime | None = None) -> bool:
    if chef.is_running() or store.profile_is_empty():
        return False
    when = next_run_at(store.get_settings(), store.last_run_start())
    return when is not None and (now or datetime.now(timezone.utc)) >= when


async def scheduler_loop(store: Store, chef: Chef) -> None:
    log.info("planificateur démarré (vérification toutes les %ss)", config.SCHEDULER_TICK_SECONDS)
    while True:
        try:
            if should_run(store, chef):
                run_id = chef.start_mission_async("auto")
                log.info("mission automatique lancée : %s", run_id)
        except Exception:
            log.exception("erreur du planificateur")
        await asyncio.sleep(config.SCHEDULER_TICK_SECONDS)
