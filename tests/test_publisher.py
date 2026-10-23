"""用本地 gh 替身检查成对发布顺序和已发布版本的重跑行为。"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(os.name == "nt", "Publisher runs on Linux")
class PublisherAcceptance(unittest.TestCase):
    def test_uploads_both_drafts_before_publishing_and_skips_published_versions(self):
        with tempfile.TemporaryDirectory(prefix="publisher-test-") as temp:
            directory = Path(temp)
            gh = directory / "gh"
            gh.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
p = pathlib.Path(os.environ["FAKE_GH_STATE"])
s = json.loads(p.read_text()) if p.exists() else {"tags": {}, "calls": []}
args = sys.argv[1:]
op, tag = args[1:3]
s["calls"].append(args)
code = 0
if op == "view":
    if tag not in s["tags"]:
        code = 1
    elif "isDraft" in args:
        print(str(s["tags"][tag]["draft"]).lower())
    else:
        print(s["tags"][tag]["target"])
elif op == "create":
    s["tags"][tag] = {"draft": True, "uploaded": False, "target": os.environ["GITHUB_SHA"]}
elif op == "upload":
    assert s["tags"][tag]["draft"]
    s["tags"][tag]["uploaded"] = True
elif op == "edit":
    assert all(t["uploaded"] for t in s["tags"].values())
    s["tags"][tag]["draft"] = False
else:
    raise AssertionError(args)
p.write_text(json.dumps(s))
sys.exit(code)
''', encoding="utf-8")
            gh.chmod(0o755)
            state = directory / "state.json"
            env = {**os.environ, "PATH": str(directory) + os.pathsep + os.environ["PATH"], "FAKE_GH_STATE": str(state), "GITHUB_SHA": "test-commit"}
            command = ["bash", str(ROOT / "tools/publish_release.sh")]
            first = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(first.returncode, 0, first.stderr)
            data = json.loads(state.read_text())
            self.assertTrue(all(not tag["draft"] for tag in data["tags"].values()))
            second = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(second.returncode, 0, second.stderr)
            calls = json.loads(state.read_text())["calls"][len(data["calls"]):]
            self.assertTrue(all(call[1] == "view" for call in calls))


if __name__ == "__main__":
    unittest.main()
