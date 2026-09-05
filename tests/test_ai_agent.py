"""Tests for the AI agent / run / diagnose features (no real network, LLM mocked)."""
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from SysAdminToolbox import SysAdminToolbox as sat  # noqa: E402


def _cap(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn(*a, **k)
    return buf.getvalue().strip()


class ExtractJsonTests(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(sat._ai_extract_json('{"final":"x"}'), {"final": "x"})

    def test_fenced(self):
        self.assertEqual(
            sat._ai_extract_json('```json\n{"tool":"net","args":["dns","x"]}\n```'),
            {"tool": "net", "args": ["dns", "x"]})

    def test_embedded(self):
        self.assertEqual(sat._ai_extract_json("sure thing: {\"a\": 1} done").get("a"), 1)

    def test_garbage_returns_empty(self):
        self.assertEqual(sat._ai_extract_json("no json at all"), {})


class ToolRunTests(unittest.TestCase):
    def test_allowed_command_runs(self):
        ok, out = sat._ai_tool_run("subnet", ["calc", "10.0.0.0/24"])
        self.assertTrue(ok)
        self.assertTrue(json.loads(out))

    def test_blocks_ai(self):
        self.assertFalse(sat._ai_tool_run("ai", ["ask", "x"])[0])

    def test_blocks_web(self):
        self.assertFalse(sat._ai_tool_run("web", [])[0])

    def test_blocks_unknown(self):
        self.assertFalse(sat._ai_tool_run("rm", ["-rf", "/"])[0])


class ConfirmCloudTests(unittest.TestCase):
    def test_ollama_needs_no_confirm(self):
        self.assertTrue(sat._ai_confirm_cloud("ollama", "m", "d", False))

    def test_cloud_with_yes(self):
        self.assertTrue(sat._ai_confirm_cloud("openai", "m", "d", True))

    def test_cloud_non_interactive_refuses(self):
        with patch.object(sat.sys, "stdin", io.StringIO()):
            with self.assertRaises(RuntimeError):
                sat._ai_confirm_cloud("openai", "m", "d", False)


class AgentTests(unittest.TestCase):
    def test_runs_tool_then_finalizes(self):
        seq = ['{"tool":"subnet","args":["calc","10.0.0.0/24"],"why":"x"}',
               '{"final":"done here"}']
        calls = []

        def fake(prompt, spec="auto", system=None):
            calls.append(prompt)
            return seq[len(calls) - 1]

        with patch.object(sat, "ai_complete", side_effect=fake), \
                patch.object(sat, "_ai_tool_run", return_value=(True, '{"hosts":254}')) as tr:
            out = _cap(sat._ai_agent, "goal", "ollama", 8)
        self.assertEqual(out, "done here")
        self.assertEqual(len(calls), 2)
        tr.assert_called_once_with("subnet", ["calc", "10.0.0.0/24"])

    def test_stops_when_no_action(self):
        with patch.object(sat, "ai_complete", return_value="I cannot help"):
            out = _cap(sat._ai_agent, "goal", "ollama", 3)
        self.assertIn("cannot", out)

    def test_budget_exhausted_forces_final(self):
        it = iter(['{"tool":"subnet","args":["calc","10.0.0.0/24"]}',
                   '{"tool":"subnet","args":["calc","10.0.0.0/24"]}',
                   '{"final":"forced answer"}'])

        with patch.object(sat, "ai_complete", side_effect=lambda *a, **k: next(it, '{"final":"forced answer"}')), \
                patch.object(sat, "_ai_tool_run", return_value=(True, "{}")):
            out = _cap(sat._ai_agent, "goal", "ollama", 2)
        self.assertEqual(out, "forced answer")


class MaybeJsonTests(unittest.TestCase):
    def test_parses_json_object(self):
        self.assertEqual(sat._ai_maybe_json('{"hosts": 254}'), {"hosts": 254})

    def test_passes_through_non_json(self):
        self.assertEqual(sat._ai_maybe_json("not json"), "not json")


class AgentJsonTests(unittest.TestCase):
    def test_json_report_structure(self):
        seq = ['{"tool":"subnet","args":["calc","10.0.0.0/24"],"why":"need hosts"}',
               '{"final":"1022 usable hosts"}']
        calls = []

        def fake(prompt, spec="auto", system=None):
            calls.append(prompt)
            return seq[len(calls) - 1]

        with patch.object(sat, "ai_complete", side_effect=fake), \
                patch.object(sat, "_ai_tool_run", return_value=(True, '{"usable_hosts":1022}')):
            out = _cap(sat._ai_agent, "how many hosts", "ollama", 8, True)
        report = json.loads(out)
        self.assertEqual(report["goal"], "how many hosts")
        self.assertTrue(report["completed"])
        self.assertEqual(report["conclusion"], "1022 usable hosts")
        self.assertEqual(len(report["steps"]), 1)
        step = report["steps"][0]
        self.assertEqual(step["command"], "subnet calc 10.0.0.0/24")
        self.assertEqual(step["why"], "need hosts")
        self.assertTrue(step["ok"])
        self.assertEqual(step["output"], {"usable_hosts": 1022})

    def test_json_budget_exhausted_marks_incomplete(self):
        it = iter(['{"tool":"subnet","args":["calc","10.0.0.0/24"]}',
                   '{"tool":"subnet","args":["calc","10.0.0.0/24"]}',
                   '{"final":"forced"}'])
        with patch.object(sat, "ai_complete", side_effect=lambda *a, **k: next(it, '{"final":"forced"}')), \
                patch.object(sat, "_ai_tool_run", return_value=(True, "{}")):
            out = _cap(sat._ai_agent, "goal", "ollama", 2, True)
        report = json.loads(out)
        self.assertFalse(report["completed"])
        self.assertEqual(report["conclusion"], "forced")
        self.assertEqual(len(report["steps"]), 2)
        self.assertIn("note", report)

    def test_json_no_action_marks_incomplete(self):
        with patch.object(sat, "ai_complete", return_value="I cannot help"):
            out = _cap(sat._ai_agent, "goal", "ollama", 3, True)
        report = json.loads(out)
        self.assertFalse(report["completed"])
        self.assertEqual(report["steps"], [])
        self.assertIn("cannot", report["conclusion"])


class RunAndDiagnoseTests(unittest.TestCase):
    def test_run_executes_proposed_command(self):
        with patch.object(sat, "ai_complete", return_value="subnet calc 10.0.0.0/24"), \
                patch.object(sat, "_ai_tool_run", return_value=(True, '{"ok":1}')) as tr:
            out = _cap(sat._ai_run, "split it", "ollama", True)
        self.assertIn("ok", out)
        tr.assert_called_once()

    def test_run_strips_sysadmintoolbox_prefix(self):
        seen = {}

        def tr(group, args):
            seen["group"] = group
            return (True, "{}")

        with patch.object(sat, "ai_complete", return_value="$ SysAdminToolbox net certcheck example.com"), \
                patch.object(sat, "_ai_tool_run", side_effect=tr):
            _cap(sat._ai_run, "check cert", "ollama", True)
        self.assertEqual(seen["group"], "net")

    def test_diagnose_runs_battery_and_narrates(self):
        with patch.object(sat, "_ai_tool_run", return_value=(True, "{}")) as tr, \
                patch.object(sat, "ai_complete", return_value="assessment text"):
            out = _cap(sat._ai_diagnose, "example.com", "slow", "ollama")
        self.assertEqual(out, "assessment text")
        self.assertGreaterEqual(tr.call_count, 4)



class PromptReferenceTests(unittest.TestCase):
    def test_suggest_prompt_includes_syntax_reference(self):
        prompt = sat._ai_build_prompt("suggest", "split a /24 into four")
        self.assertIn("subnet calc", prompt)
        self.assertIn("split a /24 into four", prompt)

    def test_reference_lists_real_commands(self):
        ref = sat._AI_CMD_REFERENCE
        for token in ("subnet calc", "subnet vlsm", "certcheck", "ipclass"):
            self.assertIn(token, ref)


if __name__ == "__main__":
    unittest.main()
