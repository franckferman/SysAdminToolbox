#!/usr/bin/env python3
"""Generate docs/data/cheatsheets.json for the SysAdminToolbox site.

Single source of truth: the data is extracted from the tool itself, so the
public site never drifts from the CLI. Re-run after changing cheatsheets.
"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SAT = ROOT / "src" / "SysAdminToolbox" / "SysAdminToolbox.py"
DATA = ROOT / "docs" / "data"
TOPICS = ["vlan", "acl", "firewall", "routing", "nat", "huawei", "mikrotik"]


def _run(*args):
    return subprocess.run([sys.executable, str(SAT), *args],
                          capture_output=True, text=True).stdout


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    cheats = {}
    for topic in TOPICS:
        raw = _run("cheat", topic, "--json")
        try:
            cheats[topic] = json.loads(raw).get("cheatsheet", "")
        except json.JSONDecodeError:
            cheats[topic] = raw.strip()
    version = (_run("--version").strip().split() or ["v0"])[-1].lstrip("v")
    payload = {"version": version, "cheatsheets": cheats}
    (DATA / "cheatsheets.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {DATA/'cheatsheets.json'} (v{version}, {len(cheats)} topics)")


if __name__ == "__main__":
    main()
