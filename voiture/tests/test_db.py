import unittest

from app.db import Store, normalize_url


class NormalizeUrlTest(unittest.TestCase):
    def test_removes_tracking_fragment_and_trailing_slash(self):
        self.assertEqual(
            normalize_url("HTTPS://WWW.Site.fr/annonce/12/?utm_source=a&id=3&fbclid=z#photos"),
            "https://www.site.fr/annonce/12?id=3",
        )

    def test_keeps_invalid_url_as_is(self):
        self.assertEqual(normalize_url("pas une url"), "pas une url")


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")

    def test_profile_defaults_and_unknown_keys_ignored(self):
        self.assertTrue(self.store.profile_is_empty())
        profile = self.store.update_profile({"budget_max": 18000, "pirate": "x"})
        self.assertEqual(profile["budget_max"], 18000)
        self.assertNotIn("pirate", profile)
        self.assertFalse(self.store.profile_is_empty())
        self.assertEqual(self.store.get_profile()["rayon_km"], 100)

    def test_settings_are_clamped(self):
        settings = self.store.update_settings({"frequence_heures": 0, "seuil_notification": 150})
        self.assertEqual(settings["frequence_heures"], 24)
        self.assertEqual(settings["seuil_notification"], 100)

    def test_upsert_dedupes_and_parses_numbers(self):
        first = self.store.upsert_listing({"url": "https://a.fr/1?utm_medium=x", "titre": "Yaris", "prix": "15 900 €"})
        second = self.store.upsert_listing({"url": "https://a.fr/1", "km": "42 000 km"})
        self.assertTrue(first[1])
        self.assertFalse(second[1])
        self.assertEqual(first[0], second[0])
        listing = self.store.get_listing(first[0])
        self.assertEqual((listing["prix"], listing["km"], listing["titre"]), (15900, 42000, "Yaris"))
        self.assertIsNone(self.store.upsert_listing({"url": "javascript:alert(1)"}))

    def test_score_is_clamped_and_analysis_decoded(self):
        lid, _ = self.store.upsert_listing({"url": "https://a.fr/2"})
        self.assertTrue(self.store.score_listing("https://a.fr/2/", 140, "Top", {"conseil": "Appeler"}))
        listing = self.store.get_listing(lid)
        self.assertEqual(listing["score"], 100)
        self.assertEqual(listing["analyse"], {"conseil": "Appeler"})

    def test_rejecting_with_feedback_is_remembered_and_hidden(self):
        lid, _ = self.store.upsert_listing({"url": "https://a.fr/3", "titre": "Clio"})
        self.store.set_listing_status(lid, "rejetee", "trop de kilomètres")
        self.assertEqual(self.store.list_listings(), [])
        self.assertEqual(len(self.store.list_listings("rejetee")), 1)
        self.assertIn("trop de kilomètres", self.store.memories()[0]["note"])
        with self.assertRaises(ValueError):
            self.store.set_listing_status(lid, "vendue")

    def test_notification_queue(self):
        lid, _ = self.store.upsert_listing({"url": "https://a.fr/4"})
        self.store.score_listing("https://a.fr/4", 80, None, None)
        self.assertEqual([l["id"] for l in self.store.listings_to_notify(75)], [lid])
        self.store.mark_notified([lid])
        self.assertEqual(self.store.listings_to_notify(75), [])

    def test_runs_journal_usage_and_stale(self):
        run = self.store.start_run("manuel")
        self.store.append_journal(run, {"agent": "prix"})
        self.store.add_usage(run, 10, 5)
        self.store.fail_stale_runs()
        data = self.store.get_run(run)
        self.assertEqual(data["statut"], "interrompue")
        self.assertEqual(data["journal"][0]["agent"], "prix")
        self.assertEqual((data["tokens_entree"], data["tokens_sortie"]), (10, 5))

    def test_push_subscriptions(self):
        self.store.add_push_subscription({"endpoint": "https://push/1", "keys": {}})
        self.store.add_push_subscription({"endpoint": "https://push/1", "keys": {"a": 1}})
        self.assertEqual(self.store.push_subscriptions(), [{"endpoint": "https://push/1", "keys": {"a": 1}}])
        self.store.remove_push_subscription("https://push/1")
        self.assertEqual(self.store.push_subscriptions(), [])
        with self.assertRaises(ValueError):
            self.store.add_push_subscription({})


if __name__ == "__main__":
    unittest.main()
