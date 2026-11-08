import unittest

from app import config
from app.agents import AGENTS, roster
from app.llm import AgentError, create_message, extract_json, run_specialist, web_tools

from fakes import FakeClient, response, text, tool_use


class ExtractJsonTest(unittest.TestCase):
    def test_fenced_and_bare(self):
        self.assertEqual(extract_json('Voici :\n```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(extract_json('bla {"b": [1, 2]} bla'), {"b": [1, 2]})
        self.assertIsNone(extract_json("rien"))
        self.assertIsNone(extract_json("[1, 2]"))


class AgentsTest(unittest.TestCase):
    def test_roster_and_tools(self):
        keys = [a["key"] for a in roster()]
        self.assertEqual(keys[0], "chef")
        self.assertEqual(set(keys[1:]), {"profil", "annonces", "concessions", "fiabilite", "prix", "couts", "verif"})
        for spec in AGENTS.values():
            self.assertIn("rapporter", spec.system)
            self.assertEqual(spec.rapport_schema["type"], "object")
        types = [t["type"] for t in web_tools(AGENTS["annonces"])]
        self.assertEqual(types, ["web_search_20260209", "web_fetch_20260209"])


class CreateMessageTest(unittest.TestCase):
    def test_fallbacks_added(self):
        client = FakeClient(lambda kw: response([text("ok")]))
        create_message(client, model="m", messages=[])
        call = client.calls[0]
        if config.USE_FALLBACKS:
            self.assertEqual(call["fallbacks"], "default")
            self.assertIn(config.FALLBACK_BETA, call["betas"])


class RunSpecialistTest(unittest.TestCase):
    spec = AGENTS["fiabilite"]

    def test_pause_turn_then_report(self):
        replies = iter([
            response([text("je cherche…")], "pause_turn"),
            response([tool_use("rapporter", {"synthese": "ok", "modeles": []})], "tool_use"),
        ])
        client = FakeClient(lambda kw: next(replies))
        usage = []
        report = run_specialist(client, self.spec, "Yaris ?", {"profil": {}}, lambda i, o: usage.append((i, o)))
        self.assertEqual(report["synthese"], "ok")
        self.assertEqual(len(usage), 2)
        # le tour en pause est renvoyé tel quel, sans message « continue » ajouté
        second = client.calls[1]["messages"]
        self.assertEqual([m["role"] for m in second], ["user", "assistant"])
        self.assertEqual(client.calls[0]["output_config"], {"effort": "medium"})

    def test_nudge_then_json_text(self):
        replies = iter([response([text("Je pense que c'est fiable.")]), response([text('{"synthese": "fiable"}')])])
        client = FakeClient(lambda kw: next(replies))
        self.assertEqual(run_specialist(client, self.spec, "?", {})["synthese"], "fiable")
        self.assertIn("rapporter", client.calls[1]["messages"][-1]["content"])

    def test_refusal_raises(self):
        client = FakeClient(lambda kw: response([], "refusal"))
        with self.assertRaises(AgentError):
            run_specialist(client, self.spec, "?", {})

    def test_gives_up_without_report(self):
        client = FakeClient(lambda kw: response([text("bof")]))
        with self.assertRaises(AgentError):
            run_specialist(client, self.spec, "?", {})
        self.assertEqual(len(client.calls), 2)


if __name__ == "__main__":
    unittest.main()
