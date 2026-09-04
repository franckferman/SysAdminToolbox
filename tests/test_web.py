"""Tests for the optional web mode (stdlib http.server, safe commands only)."""
import json
import sys
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from SysAdminToolbox import SysAdminToolbox as sat  # noqa: E402


class WebWhitelistTests(unittest.TestCase):
    def test_net_is_blocked(self):
        ok, out = sat._web_run("net ping 8.8.8.8", True)
        self.assertFalse(ok)
        self.assertIn("not available", out)

    def test_ai_is_blocked(self):
        ok, _ = sat._web_run("ai ask hello", True)
        self.assertFalse(ok)

    def test_web_is_blocked(self):
        ok, _ = sat._web_run("web", True)
        self.assertFalse(ok)

    def test_empty_line(self):
        ok, _ = sat._web_run("", True)
        self.assertFalse(ok)

    def test_safe_subnet_json(self):
        ok, out = sat._web_run("subnet calc 192.168.0.0/24", True)
        self.assertTrue(ok)
        self.assertTrue(json.loads(out))

    def test_safe_cheat_text(self):
        ok, out = sat._web_run("cheat vlan", False)
        self.assertTrue(ok)
        self.assertIn("VLAN", out)

    def test_alias_is_allowed(self):
        ok, out = sat._web_run("s calc 10.0.0.0/24", True)  # 's' == subnet
        self.assertTrue(ok)


class WebServerTests(unittest.TestCase):
    def setUp(self):
        self.httpd = HTTPServer(("127.0.0.1", 0), sat._make_web_handler())
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def _get(self, path):
        url = "http://127.0.0.1:%d%s" % (self.port, path)
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode()

    def test_root_serves_html(self):
        status, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn("SysAdminToolbox", body)

    def test_api_run_safe_command(self):
        q = urllib.parse.quote("subnet calc 192.168.0.0/24")
        status, body = self._get("/api/run?json=1&line=" + q)
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data["ok"])

    def test_api_run_blocked_command_returns_400(self):
        q = urllib.parse.quote("net ping 8.8.8.8")
        status, body = self._get("/api/run?line=" + q)
        self.assertEqual(status, 400)
        self.assertFalse(json.loads(body)["ok"])

    def test_unknown_path_404(self):
        status, _ = self._get("/nope")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
