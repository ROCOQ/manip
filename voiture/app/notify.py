"""Notifications : Web Push (iPhone/Mac, app installée) et ntfy (optionnel)."""
from __future__ import annotations

import base64
import json
import logging
import urllib.request

from . import config
from .db import Store

log = logging.getLogger("voiture.notify")


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def ensure_vapid(store: Store) -> dict:
    """Clés VAPID générées une fois puis conservées dans la base."""
    keys = store.get_kv("vapid")
    if keys:
        return keys
    from cryptography.hazmat.primitives import serialization
    from py_vapid import Vapid

    vapid = Vapid()
    vapid.generate_keys()
    public = vapid.public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    keys = {"private_pem": vapid.private_pem().decode(), "public_key": _b64url(public)}
    store.set_kv("vapid", keys)
    return keys


def send_webpush(store: Store, payload: dict) -> int:
    """Envoie la notification à tous les appareils abonnés. Renvoie le nombre d'envois réussis."""
    subscriptions = store.push_subscriptions()
    if not subscriptions:
        return 0
    from py_vapid import Vapid
    from pywebpush import WebPushException, webpush

    vapid = Vapid.from_pem(ensure_vapid(store)["private_pem"].encode())
    sent = 0
    for sub in subscriptions:
        try:
            webpush(
                subscription_info=sub,
                data=json.dumps(payload, ensure_ascii=False),
                vapid_private_key=vapid,
                vapid_claims={"sub": config.VAPID_CONTACT},
                ttl=24 * 3600,
                timeout=15,
            )
            sent += 1
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (404, 410):
                store.remove_push_subscription(sub.get("endpoint", ""))
                log.info("abonnement expiré supprimé")
            else:
                log.warning("échec Web Push (%s) : %s", status, exc)
        except Exception:
            log.exception("échec Web Push")
    return sent


def send_ntfy(topic: str, title: str, message: str, click_url: str | None = None) -> bool:
    if not topic:
        return False
    body = {"topic": topic, "title": title, "message": message, "tags": ["red_car"], "priority": 4}
    if click_url:
        body["click"] = click_url
    request = urllib.request.Request(
        config.NTFY_SERVER.rstrip("/"),
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return 200 <= response.status < 300
    except Exception as exc:
        log.warning("échec ntfy : %s", exc)
        return False


def build_notification(report: dict, listings: list[dict]) -> dict | None:
    """Construit la notification de fin de mission, ou None s'il n'y a rien à signaler."""
    if not listings and not report.get("notifier"):
        return None
    if listings:
        n = len(listings)
        title = f"🚗 {n} nouvelle{'s' if n > 1 else ''} piste{'s' if n > 1 else ''} intéressante{'s' if n > 1 else ''}"
        lines = []
        for l in listings[:3]:
            prix = f"{l['prix']:,} €".replace(",", " ") if l.get("prix") else "prix ?"
            lines.append(f"{l.get('score', '?')}/100 · {l.get('titre') or 'Annonce'} · {prix}")
        body = "\n".join(lines)
    else:
        title = "🚗 Du nouveau dans votre recherche"
        body = ""
    message = (report.get("message_notification") or "").strip()
    if message:
        body = f"{message}\n{body}".strip()
    return {"title": title, "body": body or "Ouvrez l'app pour voir le rapport.", "url": "/#annonces"}


def make_notifier(store: Store, public_url: str | None = None):
    """Fonction appelée par le chef à la fin de chaque mission."""

    def notify(report: dict) -> None:
        settings = store.get_settings()
        listings = store.listings_to_notify(int(settings.get("seuil_notification", 75)))
        payload = build_notification(report, listings)
        if payload is None:
            return
        send_webpush(store, payload)
        send_ntfy(settings.get("ntfy_topic", ""), payload["title"], payload["body"],
                  (public_url.rstrip("/") + "/#annonces") if public_url else None)
        store.mark_notified([l["id"] for l in listings])

    return notify
