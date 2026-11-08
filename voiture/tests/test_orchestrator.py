import json
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from app import config
from app.db import Store, normalize_url
from app.orchestrator import Chef
from app.scheduler import next_run_at, should_run

from fakes import LISTING_A, LISTING_B, FakeClient, mission_router, response, text, tool_use


class MissionTest(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.store.update_profile({"budget_max": 17000, "localisation": "Lyon"})
        self.notified = []
        self.client = FakeClient(mission_router)
        self.chef = Chef(self.store, client=self.client, notifier=self.notified.append)

    def test_full_mission(self):
        run_id = self.chef.run_mission_blocking("manuel")
        run = self.store.get_run(run_id)
        self.assertEqual(run["statut"], "terminee", run["erreur"])
        self.assertEqual(run["rapport"]["resume"], "La Yaris est la meilleure piste.")

        # journal : profil, annonces, prix + verif (parallèle), rapport du chef
        agents = [step["agent"] for step in run["journal"]]
        self.assertEqual(agents[:2], ["profil", "annonces"])
        self.assertEqual(sorted(agents[2:4]), ["prix", "verif"])
        self.assertEqual(agents[-1], "chef")
        self.assertGreater(run["tokens_entree"], 0)

        # annonces enregistrées (l'URL invalide est ignorée), dédoublonnées et notées
        listings = {l["url"]: l for l in self.store.list_listings()}
        self.assertEqual(set(listings), {normalize_url(LISTING_A["url"]), normalize_url(LISTING_B["url"])})
        yaris = listings[normalize_url(LISTING_A["url"])]
        self.assertEqual((yaris["prix"], yaris["score"], yaris["verdict"]), (15900, 88, "À appeler vite"))
        self.assertEqual(yaris["analyse"]["conseil"], "Négocier à 15 200 €")
        self.assertEqual(listings[normalize_url(LISTING_B["url"])]["score"], 100)

        # mémoire et notification
        self.assertIn("La Yaris 4 hybride est très fiable.", [m["note"] for m in self.store.memories()])
        self.assertEqual(len(self.notified), 1)

        # le détective a reçu les détails de l'annonce demandée
        verif_call = next(c for c in self.client.calls if "« Détective anti-arnaque »" in c["system"])
        context = verif_call["messages"][0]["content"]
        self.assertIn("Toyota Yaris Hybride 2021", context)

        # tous les résultats d'outils parallèles sont renvoyés dans un seul message utilisateur
        last_chef = [c for c in self.client.calls if "Tu es le chef" in c["system"]][-1]
        parallel = last_chef["messages"][-1]["content"]
        self.assertEqual(len(parallel), 2)
        self.assertTrue(all(r["type"] == "tool_result" for r in parallel))

    def test_second_mission_marks_known_listings(self):
        self.chef.run_mission_blocking("manuel")
        self.chef.run_mission_blocking("auto")
        run = self.store.list_runs(1)[0]
        annonces = next(s for s in run["journal"] if s["agent"] == "annonces")["rapport"]["annonces"]
        self.assertTrue(all(a["nouvelle"] is False for a in annonces))

    def test_agent_budget_is_enforced(self):
        def router(kwargs):
            if "Tu es le chef" in kwargs["system"]:
                last = kwargs["messages"][-1]["content"]
                if isinstance(last, list) and "Budget de consultations" in last[0]["content"]:
                    return response([tool_use("publier_rapport", {"resume": "stop", "classement": [], "notifier": False})], "tool_use")
                return response([tool_use("consulter_agent", {"agent": "fiabilite", "consigne": "?"})], "tool_use")
            return response([tool_use("rapporter", {"synthese": "ok"})], "tool_use")

        chef = Chef(self.store, client=FakeClient(router))
        with mock.patch.object(config, "MAX_AGENT_CALLS", 2):
            run_id = chef.run_mission_blocking("manuel")
        run = self.store.get_run(run_id)
        self.assertEqual(run["rapport"]["resume"], "stop")
        self.assertEqual(sum(1 for s in run["journal"] if s["agent"] == "fiabilite"), 2)

    def test_agent_failure_does_not_kill_mission(self):
        def router(kwargs):
            if "Tu es le chef" in kwargs["system"]:
                if any(m["role"] == "assistant" for m in kwargs["messages"]):
                    return response([tool_use("publier_rapport", {"resume": "partiel", "classement": [], "notifier": False})], "tool_use")
                return response([tool_use("consulter_agent", {"agent": "prix", "consigne": "?"})], "tool_use")
            raise ConnectionError("réseau coupé")

        chef = Chef(self.store, client=FakeClient(router))
        run = self.store.get_run(chef.run_mission_blocking("manuel"))
        self.assertEqual(run["statut"], "terminee")
        self.assertIn("indisponible", run["journal"][0]["rapport"]["erreur"])

    def test_chef_crash_marks_run_failed(self):
        def router(kwargs):
            raise RuntimeError("API en panne")

        chef = Chef(self.store, client=FakeClient(router))
        run = self.store.get_run(chef.run_mission_blocking("manuel"))
        self.assertEqual(run["statut"], "echec")
        self.assertIn("API en panne", run["erreur"])

    def test_only_one_mission_at_a_time(self):
        gate = mock.Mock()

        def slow_router(kwargs):
            time.sleep(0.3)
            return mission_router(kwargs)

        chef = Chef(self.store, client=FakeClient(slow_router), notifier=gate)
        first = chef.start_mission_async("manuel")
        self.assertIsNotNone(first)
        self.assertTrue(chef.is_running())
        self.assertIsNone(chef.start_mission_async("manuel"))
        for _ in range(100):
            if not chef.is_running():
                break
            time.sleep(0.1)
        self.assertFalse(chef.is_running())
        self.assertEqual(self.store.get_run(first)["statut"], "terminee")


class ChatTest(unittest.TestCase):
    def test_chat_updates_profile_and_memory(self):
        store = Store(":memory:")

        def router(kwargs):
            if any(m["role"] == "assistant" for m in kwargs["messages"]):
                return response([text("C'est noté : budget 15 000 €. Combien de km par an ?")])
            return response([
                tool_use("mettre_a_jour_profil", {"modifications": {"budget_max": 15000}}),
                tool_use("memoriser", {"note": "A un chien, veut un grand coffre."}),
            ], "tool_use")

        chef = Chef(store, client=FakeClient(router))
        answer = chef.chat_blocking("J'ai 15 000 € et un chien.")
        self.assertIn("15 000", answer)
        self.assertEqual(store.get_profile()["budget_max"], 15000)
        self.assertEqual(store.memories()[0]["note"], "A un chien, veut un grand coffre.")
        self.assertEqual([m["role"] for m in store.chat_history()], ["user", "assistant"])

    def test_chat_can_launch_mission(self):
        store = Store(":memory:")
        store.update_profile({"budget_max": 15000})
        launched = {}

        def router(kwargs):
            if "Tu discutes" not in kwargs["system"]:
                return mission_router(kwargs)
            if any(m["role"] == "assistant" for m in kwargs["messages"]):
                results = kwargs["messages"][-1]["content"]
                launched.update(json.loads(results[0]["content"]))
                return response([text("Mission lancée !")])
            return response([tool_use("lancer_mission", {"consigne": "Yaris"})], "tool_use")

        chef = Chef(store, client=FakeClient(router))
        self.assertEqual(chef.chat_blocking("Lance la recherche"), "Mission lancée !")
        self.assertTrue(launched["ok"])
        for _ in range(100):
            if not chef.is_running():
                break
            time.sleep(0.05)
        self.assertEqual(store.get_run(launched["mission"])["declencheur"], "chat")


class SchedulerTest(unittest.TestCase):
    def test_next_run(self):
        self.assertIsNone(next_run_at({"recherche_auto": False}, None))
        start = "2026-11-08T08:00:00+00:00"
        self.assertEqual(
            next_run_at({"recherche_auto": True, "frequence_heures": 6}, start),
            datetime(2026, 11, 8, 14, tzinfo=timezone.utc),
        )

    def test_should_run(self):
        store = Store(":memory:")
        chef = Chef(store, client=FakeClient(mission_router))
        self.assertFalse(should_run(store, chef))  # profil vide : on attend
        store.update_profile({"budget_max": 15000})
        self.assertTrue(should_run(store, chef))
        run = store.start_run("auto")
        store.finish_run(run, "terminee")
        self.assertFalse(should_run(store, chef))
        later = datetime.now(timezone.utc) + timedelta(hours=25)
        self.assertTrue(should_run(store, chef, now=later))


if __name__ == "__main__":
    unittest.main()
