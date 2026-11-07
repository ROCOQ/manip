import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import check_wiiu_files as c  # noqa: E402


def make_dump(root: Path, complete: bool = True) -> Path:
    for d in ("code", "content", "meta"):
        (root / d).mkdir(parents=True)
    (root / "code" / "game.rpx").write_bytes(b"\0" * 10)
    if complete:
        (root / "code" / "app.xml").write_text("x")
        (root / "code" / "cos.xml").write_text("x")
        (root / "meta" / "meta.xml").write_text("x")
    return root


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_complete_dump(self):
        make_dump(self.root / "Jeu")
        titles = c.scan(self.root)
        self.assertEqual(len(titles), 1)
        self.assertTrue(titles[0].ok)

    def test_incomplete_dump(self):
        make_dump(self.root / "Jeu", complete=False)
        self.assertFalse(c.scan(self.root)[0].ok)

    def test_root_is_dump(self):
        make_dump(self.root / "Jeu")
        self.assertEqual(len(c.scan(self.root / "Jeu")), 1)

    def test_wux_magic(self):
        (self.root / "a.wux").write_bytes(b"WUX0" + b"\0" * 10)
        (self.root / "b.wux").write_bytes(b"NOPE")
        res = {Path(t.path).name: t.ok for t in c.scan(self.root)}
        self.assertEqual(res, {"a.wux": True, "b.wux": False})

    def test_wud_size(self):
        (self.root / "a.wud").write_bytes(b"\0" * 100)
        t = c.scan(self.root)[0]
        self.assertTrue(t.needs_keys)
        self.assertFalse(t.ok)

    def test_keys(self):
        k = self.root / "keys.txt"
        k.write_text("# commentaire\n" + "a" * 32 + " # Mon jeu\n\nzzz\n")
        valid, problems = c.check_keys(k)
        self.assertEqual(valid, 1)
        self.assertEqual(len(problems), 1)

    def test_main_exit_codes(self):
        make_dump(self.root / "Jeu")
        self.assertEqual(c.main([str(self.root)]), 0)
        (self.root / "b.wux").write_bytes(b"NOPE")
        self.assertEqual(c.main([str(self.root)]), 1)
        self.assertEqual(c.main([str(self.root / "absent")]), 2)


if __name__ == "__main__":
    unittest.main()
