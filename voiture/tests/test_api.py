import os
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ["VOITURE_NO_AUTOAPP"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

from app import config, notify  # noqa: E402
from app.db import Store  # noqa: E402
from app.main import create_app  # noqa: E402
from app.orchestrator import Chef  # noqa: E402

from fakes import FakeClient, mission_router  # noqa: E402


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.chef = Chef(self.store, client=FakeClient(mission_router))
        with mock.patch.object(config, "APP_TOKEN", "secret"):
            self.app = create_app(self.store, self.chef, scheduler=False)
        self.client = TestClient(self.app)
        self.h = {"Authorization": "Bearer secret"}

    def test_pages_are_public_api_is_not(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertIn("serviceWorker", self.client.get("/static/app.js").text)
        self.assertEqual(self.client.get("/sw.js").headers["content-type"].split(";")[0], "text/javascript")
        self.assertEqual(self.client.get("/manifest.webmanifest").json()["display"], "standalone")
        self.assertEqual(self.client.get("/api/status").status_code, 401)
        self.assertEqual(self.client.get("/api/status", headers={"Authorization": "Bearer faux"}).status_code, 401)
        self.assertEqual(self.client.get("/api/status", headers=self.h).status_code, 200)

    def test_profile_and_settings_roundtrip(self):
        r = self.client.put("/api/profile", json={"budget_max": 20000, "energies": ["hybride"]}, headers=self.h)
        self.assertEqual(r.json()["energies"], ["hybride"])
        self.assertFalse(self.client.get("/api/status", headers=self.h).json()["profil_vide"])
        r = self.client.put("/api/settings", json={"frequence_heures": 6, "ntfy_topic": "abc"}, headers=self.h)
        self.assertEqual(r.json()["frequence_heures"], 6)

    def test_mission_listing_feedback_flow(self):
        self.store.update_profile({"budget_max": 17000})
        self.chef.run_mission_blocking("manuel")
        missions = self.client.get("/api/missions", headers=self.h).json()
        self.assertEqual(missions[0]["statut"], "terminee")
        detail = self.client.get(f"/api/missions/{missions[0]['id']}", headers=self.h).json()
        self.assertGreaterEqual(len(detail["journal"]), 4)

        listings = self.client.get("/api/listings", headers=self.h).json()
        self.assertEqual(listings[0]["score"], 100)
        lid = listings[0]["id"]
        r = self.client.post(f"/api/listings/{lid}/status", json={"statut": "rejetee", "feedback": "trop loin"}, headers=self.h)
        self.assertEqual(r.json()["statut"], "rejetee")
        self.assertEqual(len(self.client.get("/api/listings", headers=self.h).json()), 1)
        self.assertEqual(self.client.post(f"/api/listings/{lid}/status", json={"statut": "x"}, headers=self.h).status_code, 400)
        self.assertEqual(self.client.post("/api/listings/999/status", json={"statut": "vue"}, headers=self.h).status_code, 404)
        self.assertTrue(any("trop loin" in m["note"] for m in self.client.get("/api/memory", headers=self.h).json()))

    def test_mission_conflict(self):
        with mock.patch.object(self.chef, "start_mission_async", return_value=None):
            self.assertEqual(self.client.post("/api/missions", json={}, headers=self.h).status_code, 409)

    def test_push_subscription_and_test(self):
        key = self.client.get("/api/push/vapid", headers=self.h).json()["publicKey"]
        self.assertGreater(len(key), 80)
        sub = {"endpoint": "https://web.push.apple.com/abc", "keys": {"p256dh": "x", "auth": "y"}}
        self.assertEqual(self.client.post("/api/push/subscribe", json=sub, headers=self.h).status_code, 200)
        with mock.patch("pywebpush.webpush") as webpush:
            r = self.client.post("/api/push/test", headers=self.h).json()
        self.assertEqual(r["web_push"], 1)
        self.assertEqual(webpush.call_args.kwargs["subscription_info"], sub)


class NotifyTest(unittest.TestCase):
    def test_vapid_keys_are_stable(self):
        store = Store(":memory:")
        self.assertEqual(notify.ensure_vapid(store), notify.ensure_vapid(store))

    def test_expired_subscription_removed(self):
        from pywebpush import WebPushException

        store = Store(":memory:")
        store.add_push_subscription({"endpoint": "https://push/gone", "keys": {}})
        err = WebPushException("gone", response=SimpleNamespace(status_code=410))
        with mock.patch("pywebpush.webpush", side_effect=err):
            self.assertEqual(notify.send_webpush(store, {"title": "t"}), 0)
        self.assertEqual(store.push_subscriptions(), [])

    def test_build_notification(self):
        self.assertIsNone(notify.build_notification({"notifier": False}, []))
        payload = notify.build_notification(
            {"message_notification": "Foncez !"},
            [{"titre": "Yaris", "prix": 15900, "score": 88}, {"titre": "Clio", "prix": None, "score": 80}],
        )
        self.assertEqual(payload["title"], "🚗 2 nouvelles pistes intéressantes")
        self.assertTrue(payload["body"].startswith("Foncez !"))
        self.assertIn("88/100 · Yaris · 15 900 €", payload["body"])

    def test_notifier_marks_listings(self):
        store = Store(":memory:")
        lid, _ = store.upsert_listing({"url": "https://a.fr/1", "titre": "Yaris"})
        store.score_listing("https://a.fr/1", 90, None, None)
        with mock.patch.object(notify, "send_webpush") as push, mock.patch.object(notify, "send_ntfy") as ntfy:
            notify.make_notifier(store)({"notifier": True})
        push.assert_called_once()
        ntfy.assert_called_once()
        self.assertEqual(store.listings_to_notify(75), [])


if __name__ == "__main__":
    unittest.main()
