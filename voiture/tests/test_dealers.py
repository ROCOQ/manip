import json
import os
import time
import unittest
from unittest import mock

os.environ["VOITURE_NO_AUTOAPP"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

from app import config  # noqa: E402
from app.agents import AGENTS  # noqa: E402
from app.db import Store, dealer_key  # noqa: E402
from app.main import create_app  # noqa: E402
from app.orchestrator import Chef  # noqa: E402

from fakes import FakeClient, response, specialist_name, text, tool_use  # noqa: E402

DEALERS_REPORT = {
    "synthese": "3 adresses sérieuses autour de Lyon.",
    "concessions": [
        {"nom": "Toyota Lyon Est", "type": "concession officielle", "marques": ["Toyota"], "ville": "Bron",
         "adresse": "12 av. Franklin Roosevelt", "distance_km": "8,5 km", "telephone": "04 72 00 00 00",
         "site": "www.toyota-lyon-est.fr", "url_stock": "https://www.toyota-lyon-est.fr/occasions",
         "note_avis": 4.6, "nb_avis": "312", "commentaire": "Label Toyota Occasions"},
        {"nom": "Garage du Centre", "ville": "Villeurbanne", "note_avis": 9},
        {"ville": "sans nom"},
    ],
}


def dealer_router(kwargs):
    if specialist_name(kwargs["system"]) == "Repéreur de concessions" or "« Repéreur de concessions »" in kwargs["system"]:
        return response([tool_use("rapporter", DEALERS_REPORT)], "tool_use")
    raise AssertionError("appel inattendu")


class DealerStoreTest(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")

    def test_key_ignores_case_and_accents(self):
        self.assertEqual(dealer_key({"nom": "Garage de l'Étoile", "ville": "Écully"}),
                         dealer_key({"nom": "GARAGE DE L ETOILE ", "ville": "ecully"}))
        self.assertEqual(dealer_key({"nom": "Auto+", "site": "https://www.autoplus.fr/x"}), "auto|autoplus.fr")
        self.assertIsNone(dealer_key({"ville": "Lyon"}))

    def test_upsert_parses_and_completes(self):
        first = self.store.upsert_dealer(DEALERS_REPORT["concessions"][0])
        d = self.store.get_dealer(first[0])
        self.assertEqual((d["distance_km"], d["nb_avis"], d["site"]), (8.5, 312, "https://www.toyota-lyon-est.fr"))
        self.assertEqual(d["marques"], ["Toyota"])
        self.assertEqual(d["statut"], "nouvelle")
        again = self.store.upsert_dealer({"nom": "toyota lyon est", "ville": "Bron", "telephone": None, "marques": "Toyota, Lexus"})
        self.assertEqual(again, (first[0], False))
        d = self.store.get_dealer(first[0])
        self.assertEqual(d["telephone"], "04 72 00 00 00")  # non écrasé par une valeur vide
        self.assertEqual(d["marques"], ["Toyota", "Lexus"])

    def test_invalid_rating_dropped_and_user_dealer_followed(self):
        did, _ = self.store.upsert_dealer({"nom": "Garage du Centre", "ville": "Villeurbanne", "note_avis": 9}, origine="utilisateur")
        d = self.store.get_dealer(did)
        self.assertIsNone(d["note_avis"])
        self.assertEqual(d["statut"], "suivie")

    def test_status_order_memory_digest_delete(self):
        far, _ = self.store.upsert_dealer({"nom": "Loin", "ville": "A", "distance_km": 40})
        near, _ = self.store.upsert_dealer({"nom": "Près", "ville": "B", "distance_km": 3})
        followed, _ = self.store.upsert_dealer({"nom": "Suivie", "ville": "C", "distance_km": 90})
        self.store.set_dealer_status(followed, "suivie")
        self.assertEqual([d["nom"] for d in self.store.list_dealers()], ["Suivie", "Près", "Loin"])
        self.store.set_dealer_status(far, "ignoree", "vendeur peu aimable")
        self.assertNotIn("Loin", [d["nom"] for d in self.store.list_dealers()])
        self.assertIn("vendeur peu aimable", self.store.memories()[0]["note"])
        self.assertEqual(self.store.dealers_digest()[0]["id"], followed)
        with self.assertRaises(ValueError):
            self.store.set_dealer_status(near, "fermee")
        self.assertTrue(self.store.delete_dealer(near))
        self.assertFalse(self.store.delete_dealer(near))


class DealerAgentTest(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.store.update_profile({"localisation": "Lyon", "rayon_km": 30, "marques_preferees": ["Toyota"]})

    def test_agent_registered(self):
        spec = AGENTS["concessions"]
        self.assertEqual(spec.nom, "Repéreur de concessions")
        self.assertIn("concessions", spec.rapport_schema["required"])
        self.assertIn("concessions", self.store.get_settings()["agents_actifs"])

    def test_consult_stores_dealers(self):
        chef = Chef(self.store, client=FakeClient(dealer_router))
        report = chef.consult("concessions", "Concessions Toyota autour de Lyon")
        self.assertEqual([c["nouvelle"] for c in report["concessions"]], [True, True])
        self.assertEqual(len(self.store.list_dealers()), 2)
        # deuxième passage : déjà connues
        report = chef.consult("concessions", "encore")
        self.assertEqual([c["nouvelle"] for c in report["concessions"]], [False, False])

    def test_known_dealers_given_to_hunter_and_chef(self):
        self.store.upsert_dealer({"nom": "Toyota Lyon Est", "ville": "Bron", "url_stock": "https://t.fr/vo"})
        chef = Chef(self.store, client=FakeClient(lambda kw: response([tool_use("rapporter", {"synthese": "ok", "annonces": []})], "tool_use")))
        chef.consult("annonces", "cherche")
        context = chef.client.calls[0]["messages"][0]["content"]
        self.assertIn("https://t.fr/vo", context)
        self.assertEqual(chef.memory_context()["concessions_connues"][0]["nom"], "Toyota Lyon Est")

    def test_background_search(self):
        chef = Chef(self.store, client=FakeClient(dealer_router))
        self.assertTrue(chef.search_dealers_async())
        for _ in range(100):
            if not chef.dealer_search_busy():
                break
            time.sleep(0.05)
        last = self.store.get_kv("derniere_recherche_concessions")
        self.assertEqual(last["nouvelles"], 2)
        self.assertFalse(last["erreur"])
        consigne = chef.client.calls[0]["messages"][0]["content"]
        self.assertIn("concessions", consigne)

    def test_chat_adds_and_dismisses_dealer(self):
        def router(kwargs):
            msgs = kwargs["messages"]
            n = sum(1 for m in msgs if m["role"] == "assistant")
            if n == 0:
                return response([tool_use("ajouter_concession", {
                    "nom": "Garage Martin", "ville": "Caluire", "telephone": "06 00 00 00 00", "marques": ["Peugeot"],
                })], "tool_use")
            if n == 1:
                added = json.loads(msgs[-1]["content"][0]["content"])
                return response([tool_use("modifier_concession", {
                    "id": added["concession"]["id"], "statut": "ignoree", "note": "trop cher",
                })], "tool_use")
            return response([text("C'est fait.")])

        chef = Chef(self.store, client=FakeClient(router))
        self.assertEqual(chef.chat_blocking("Ajoute le garage Martin à Caluire puis écarte-le"), "C'est fait.")
        dealer = self.store.list_dealers("ignoree")[0]
        self.assertEqual((dealer["nom"], dealer["origine"], dealer["notes_utilisateur"]), ("Garage Martin", "utilisateur", "trop cher"))
        tools = {t["name"] for t in chef.client.calls[0]["tools"]}
        self.assertTrue({"ajouter_concession", "modifier_concession", "consulter_agent"} <= tools)


class DealerApiTest(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.chef = Chef(self.store, client=FakeClient(dealer_router))
        with mock.patch.object(config, "APP_TOKEN", "secret"):
            self.client = TestClient(create_app(self.store, self.chef, scheduler=False))
        self.h = {"Authorization": "Bearer secret"}

    def test_crud(self):
        r = self.client.post("/api/dealers", json={"nom": "Garage Martin", "ville": "Caluire", "marques": ["Peugeot"],
                                                   "site": "garage-martin.fr"}, headers=self.h)
        self.assertEqual(r.status_code, 200)
        dealer = r.json()
        self.assertEqual((dealer["statut"], dealer["site"]), ("suivie", "https://garage-martin.fr"))
        self.assertEqual(self.client.post("/api/dealers", json={"nom": " ", "ville": "x"}, headers=self.h).status_code, 400)

        listing = self.client.get("/api/dealers", headers=self.h).json()
        self.assertEqual(len(listing["concessions"]), 1)
        self.assertFalse(listing["recherche_en_cours"])

        did = dealer["id"]
        r = self.client.post(f"/api/dealers/{did}/status", json={"statut": "ignoree", "notes": "fermé le samedi"}, headers=self.h)
        self.assertEqual(r.json()["statut"], "ignoree")
        self.assertEqual(self.client.get("/api/dealers", headers=self.h).json()["concessions"], [])
        self.assertEqual(len(self.client.get("/api/dealers?statut=ignoree", headers=self.h).json()["concessions"]), 1)
        self.assertEqual(self.client.get("/api/dealers?statut=x", headers=self.h).status_code, 400)
        self.assertEqual(self.client.post(f"/api/dealers/{did}/status", json={"statut": "x"}, headers=self.h).status_code, 400)
        self.assertEqual(self.client.delete(f"/api/dealers/{did}", headers=self.h).status_code, 200)
        self.assertEqual(self.client.delete(f"/api/dealers/{did}", headers=self.h).status_code, 404)

    def test_search_needs_location_and_runs(self):
        self.assertEqual(self.client.post("/api/dealers/search", json={}, headers=self.h).status_code, 400)
        self.store.update_profile({"localisation": "Lyon"})
        self.assertEqual(self.client.post("/api/dealers/search", json={}, headers=self.h).status_code, 200)
        for _ in range(100):
            if not self.chef.dealer_search_busy():
                break
            time.sleep(0.05)
        data = self.client.get("/api/dealers", headers=self.h).json()
        self.assertEqual(len(data["concessions"]), 2)
        self.assertEqual(data["derniere_recherche"]["nouvelles"], 2)
        with mock.patch.object(self.chef, "search_dealers_async", return_value=False):
            self.assertEqual(self.client.post("/api/dealers/search", json={}, headers=self.h).status_code, 409)


if __name__ == "__main__":
    unittest.main()
