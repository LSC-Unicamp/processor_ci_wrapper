from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import temporary_config_patch


class TemporaryConfigPatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(
            prefix="processor-ci-wrapper-patch-test-"
        )
        self.root = Path(self.temporary_directory.name)
        self.repo = self.root / "core"
        self.config_dir = self.root / "config" / "cores"
        self.comments_dir = self.root / "config" / "comments"
        self.repo.mkdir()
        self.config_dir.mkdir(parents=True)
        self.comments_dir.mkdir(parents=True)

        self.git("init")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")
        self.source = self.repo / "core.v"
        self.source.write_text("old\n", encoding="utf-8")
        self.git("add", "core.v")
        self.git("commit", "-m", "base")

        self.source.write_text("new\n", encoding="utf-8")
        patch_text = self.git("diff", "--binary", "HEAD").stdout
        self.patch_path = self.comments_dir / "core.patch"
        self.patch_path.write_text(patch_text, encoding="utf-8")
        self.git("restore", "core.v")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def git(self, *arguments: str, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *arguments],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=check,
        )

    def test_applies_patch_and_restores_clean_checkout(self) -> None:
        with temporary_config_patch(
            {"patch": "core.patch"}, self.config_dir, self.repo
        ):
            self.assertEqual(self.source.read_text(encoding="utf-8"), "new\n")

        self.assertEqual(self.source.read_text(encoding="utf-8"), "old\n")
        self.assertFalse(self.git("status", "--porcelain").stdout)

    def test_leaves_already_applied_patch_unchanged(self) -> None:
        self.git("apply", str(self.patch_path))

        with temporary_config_patch(
            {"patch": "core.patch"}, self.config_dir, self.repo
        ):
            self.assertEqual(self.source.read_text(encoding="utf-8"), "new\n")

        self.assertEqual(self.source.read_text(encoding="utf-8"), "new\n")

    def test_rejects_patch_that_neither_applies_nor_reverses(self) -> None:
        self.source.write_text("unrelated\n", encoding="utf-8")

        with self.assertRaisesRegex(RuntimeError, "cannot be applied or reversed"):
            with temporary_config_patch(
                {"patch": "core.patch"}, self.config_dir, self.repo
            ):
                self.fail("invalid patch entered the wrapper-generation scope")

        self.assertEqual(self.source.read_text(encoding="utf-8"), "unrelated\n")


if __name__ == "__main__":
    unittest.main()
