from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from Learning.registry.save_registry import save_registry


class SaveRegistryTests(unittest.TestCase):
    def test_save_registry_writes_json_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "registry.json"

            save_registry(path, {"models": {"m1": {"is_active": True}}})

            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {"models": {"m1": {"is_active": True}}},
            )

    def test_replace_failure_keeps_existing_registry_and_removes_temp_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "registry.json"
            path.write_text('{"models": {"old": true}}\n', encoding="utf-8")

            with mock.patch("Learning.registry.save_registry.os.replace", side_effect=RuntimeError("boom")):
                with self.assertRaisesRegex(RuntimeError, "boom"):
                    save_registry(path, {"models": {"new": True}})

            self.assertEqual(path.read_text(encoding="utf-8"), '{"models": {"old": true}}\n')
            self.assertEqual(list(Path(tmp).glob(".registry.json.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
