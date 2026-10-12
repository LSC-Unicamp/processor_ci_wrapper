from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import run_config_pre_script


class ConfigPreScriptTests(unittest.TestCase):
    def test_runs_in_processor_checkout(self) -> None:
        with tempfile.TemporaryDirectory(prefix="processor-ci-pre-script-") as directory:
            checkout = Path(directory)
            run_config_pre_script(
                {"pre_script": "touch dependency-ready"}, checkout
            )
            self.assertTrue((checkout / "dependency-ready").is_file())

    def test_reports_command_failure(self) -> None:
        with tempfile.TemporaryDirectory(prefix="processor-ci-pre-script-") as directory:
            with self.assertRaisesRegex(RuntimeError, "pre-script failed"):
                run_config_pre_script(
                    {"pre_script": "exit 7"}, Path(directory)
                )


if __name__ == "__main__":
    unittest.main()
