import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.deploy_mac import build_steps


class MacDeployScriptTests(unittest.TestCase):
    def test_build_steps_defaults_to_full_baostock_bootstrap(self):
        steps = build_steps()
        commands = [step["command"] for step in steps]

        self.assertIn("mkdir -p data/market data/db", commands)
        self.assertIn("PYTHONPATH=backend .venv/bin/python -m app.data.downloader --mode full", commands)
        self.assertIn(
            ".venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend",
            commands,
        )


if __name__ == "__main__":
    unittest.main()
