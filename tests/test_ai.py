"""Tests for the optional AI assistant (stdlib urllib, no real network)."""
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from SysAdminToolbox import SysAdminToolbox as sat  # noqa: E402


class _FakeResp:
    """Minimal context-manager HTTP response for mocking urlopen."""
    def __init__(self, obj):
        self._body = json.dumps(obj).encode()
    def read(self):
        return self._body
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


class DigestAndPromptTests(unittest.TestCase):
    def test_prompt_digest_is_stable_and_prefixed(self):
        d1 = sat._ai_prompt_digest("hello")
        d2 = sat._ai_prompt_digest("hello")
        self.assertEqual(d1, d2)
        self.assertTrue(d1.startswith("sha256:"))
        self.assertNotEqual(d1, sat._ai_prompt_digest("world"))

    def test_build_prompt(self):
        self.assertEqual(sat._ai_build_prompt("ask", "what is nat"), "what is nat")
        self.assertIn("Explain", sat._ai_build_prompt("explain", "DATA"))
        self.assertIn("DATA", sat._ai_build_prompt("explain", "DATA"))
        self.assertIn("command line", sat._ai_build_prompt("suggest", "split /24"))


class ProviderResolutionTests(unittest.TestCase):
    def test_auto_prefers_reachable_ollama(self):
        with patch.object(sat, "_ai_ollama_reachable", return_value=True):
            self.assertEqual(sat._ai_resolve_provider("auto"), ("ollama", sat._AI_OLLAMA_DEFAULT))

    def test_auto_falls_back_to_first_cloud_key(self):
        with patch.object(sat, "_ai_ollama_reachable", return_value=False), \
                patch.dict("os.environ", {"OPENAI_API_KEY": "x"}, clear=True):
            provider, model = sat._ai_resolve_provider("auto")
            self.assertEqual(provider, "openai")
            self.assertEqual(model, sat._AI_CLOUD["openai"][1])

    def test_explicit_provider_default_model(self):
        self.assertEqual(sat._ai_resolve_provider("anthropic"),
                         ("anthropic", sat._AI_CLOUD["anthropic"][1]))

    def test_provider_with_explicit_model(self):
        self.assertEqual(sat._ai_resolve_provider("anthropic:claude-x"),
                         ("anthropic", "claude-x"))

    def test_ollama_with_model(self):
        self.assertEqual(sat._ai_resolve_provider("ollama:mistral"), ("ollama", "mistral"))

    def test_unknown_provider_raises(self):
        with self.assertRaises(ValueError):
            sat._ai_resolve_provider("bogus")


class CompletionTests(unittest.TestCase):
    def test_anthropic_completion(self):
        resp = _FakeResp({"content": [{"text": "ANTHROPIC-OK"}]})
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "k"}, clear=True), \
                patch("urllib.request.urlopen", return_value=resp):
            self.assertEqual(sat.ai_complete("hi", "anthropic"), "ANTHROPIC-OK")

    def test_openai_compat_completion(self):
        resp = _FakeResp({"choices": [{"message": {"content": "OPENAI-OK"}}]})
        with patch.dict("os.environ", {"OPENAI_API_KEY": "k"}, clear=True), \
                patch("urllib.request.urlopen", return_value=resp):
            self.assertEqual(sat.ai_complete("hi", "openai"), "OPENAI-OK")

    def test_deepseek_uses_openai_shape(self):
        resp = _FakeResp({"choices": [{"message": {"content": "DS-OK"}}]})
        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "k"}, clear=True), \
                patch("urllib.request.urlopen", return_value=resp):
            self.assertEqual(sat.ai_complete("hi", "deepseek"), "DS-OK")

    def test_missing_cloud_key_raises_runtime(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError):
                sat.ai_complete("hi", "openai")

    def test_network_error_becomes_runtime(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "k"}, clear=True), \
                patch("urllib.request.urlopen",
                      side_effect=urllib.error.URLError("boom")):
            with self.assertRaises(RuntimeError):
                sat.ai_complete("hi", "openai")

    def test_ollama_completion(self):
        resp = _FakeResp({"response": "OLLAMA-OK"})
        with patch.dict("os.environ", {}, clear=True), \
                patch("urllib.request.urlopen", return_value=resp):
            self.assertEqual(sat.ai_complete("hi", "ollama"), "OLLAMA-OK")


if __name__ == "__main__":
    unittest.main()
