import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import steam_cloud_check as s  # noqa: E402

CATALOG = [
    {"title": "Cyberpunk 2077", "steamUrl": "https://store.steampowered.com/app/1091500",
     "store": "Steam", "status": "AVAILABLE", "isFullyOptimized": True},
    {"title": "The Witcher® 3: Wild Hunt", "steamUrl": "", "store": "Steam",
     "status": "AVAILABLE"},
    {"title": "Hades", "steamUrl": "https://store.steampowered.com/app/1145360",
     "store": "Epic Games Store", "status": "AVAILABLE"},
    {"title": "Old Game", "steamUrl": "https://store.steampowered.com/app/42",
     "store": "Steam", "status": "MAINTENANCE"},
]


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.catalog = s.parse_catalog(CATALOG)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        p = self.dir / name
        p.write_text(text, encoding="utf-8")
        return p

    def test_normalize(self):
        self.assertEqual(s.normalize("The Witcher® 3: Wild Hunt - GOTY Edition"),
                         s.normalize("The Witcher 3 Wild Hunt"))
        self.assertEqual(s.normalize("Pokémon"), "pokemon")

    def test_parse_catalog_appid(self):
        self.assertEqual(self.catalog[0].appid, 1091500)
        self.assertIsNone(self.catalog[1].appid)

    def test_text_library(self):
        lib = self.write("jeux.txt", "# mes jeux\n1091500\nThe Witcher 3: Wild Hunt\n"
                                     "https://store.steampowered.com/app/999/Truc/\n\n")
        games = s.load_library(lib)
        self.assertEqual([g.appid for g in games], [1091500, None, 999])

    def test_csv_library(self):
        lib = self.write("jeux.csv", "appid,name\n1091500,Cyberpunk 2077\n,Hades\n")
        games = s.load_library(lib)
        self.assertEqual(games[0].appid, 1091500)
        self.assertEqual(games[1].name, "Hades")

    def test_steam_api_json(self):
        data = {"response": {"game_count": 1, "games": [
            {"appid": 1091500, "name": "Cyberpunk 2077", "playtime_forever": 600}]}}
        lib = self.write("owned.json", json.dumps(data))
        games = s.load_library(lib)
        self.assertEqual(games[0].playtime_min, 600)

    def test_compare(self):
        games = [s.Game("appid 1091500", 1091500), s.Game("The Witcher 3: Wild Hunt GOTY"),
                 s.Game("Hades"), s.Game("Old Game", 42), s.Game("Inconnu")]
        res = {r.name: r for r in s.compare(games, self.catalog)}
        self.assertTrue(res["Cyberpunk 2077"].on_gfn)
        self.assertEqual(res["Cyberpunk 2077"].match, "appid")
        self.assertEqual(res["The Witcher 3: Wild Hunt GOTY"].match, "titre")
        self.assertFalse(res["Hades"].on_gfn)       # dispo seulement sur Epic
        self.assertFalse(res["Old Game"].on_gfn)    # en maintenance
        self.assertFalse(res["Inconnu"].on_gfn)

    def test_sort_playable_first(self):
        games = [s.Game("Inconnu"), s.Game("Cyberpunk 2077", 1091500)]
        self.assertTrue(s.compare(games, self.catalog)[0].on_gfn)

    def test_bad_steamid(self):
        with self.assertRaises(ValueError):
            s.fetch_owned_games("monpseudo", "cle")

    def test_main_json(self):
        lib = self.write("jeux.txt", "1091500\nInconnu\n")
        cat = self.write("cat.json", json.dumps(CATALOG))
        import contextlib, io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = s.main(["--library", str(lib), "--catalog", str(cat), "--json"])
        self.assertEqual(code, 0)
        out = json.loads(buf.getvalue())
        self.assertEqual((out["total"], out["on_gfn"]), (2, 1))


if __name__ == "__main__":
    unittest.main()
