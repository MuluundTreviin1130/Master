from __future__ import annotations

import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from Learning.registry.update_model_status import update_model_status
from Learning.runtime.resolve_model import resolve_model


class _Family:
    """Minimal family stub so resolve_model never imports full settings graphs."""

    def __init__(self, family_hash: str) -> None:
        self.family_hash = family_hash


class ResolveModelSelectionTests(unittest.TestCase):
    def _write_registry(self, root: Path, payload: dict) -> Path:
        path = root / "registry.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def _settings(self, registry_path: Path) -> types.SimpleNamespace:
        return types.SimpleNamespace(
            learning=types.SimpleNamespace(registry_path=str(registry_path)),
            validation=None,
        )

    def test_active_native_fallback_prefers_newest_eligible_model(self) -> None:
        family_hash = "family-hash"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            older_artifact = root / "older.joblib"
            newer_artifact = root / "newer.joblib"
            older_artifact.write_bytes(b"old")
            newer_artifact.write_bytes(b"new")
            registry_path = self._write_registry(
                root,
                {
                    "families": {
                        family_hash: {
                            # No preferred_model_id: reproduces the checked-in
                            # multi-active native family failure mode.
                        }
                    },
                    "models": {
                        family_hash: {
                            "native_older": {
                                "source": "native_training",
                                "artifact_path": str(older_artifact),
                                "is_active": True,
                                "is_preferred": False,
                                "validation_stage": "eligible",
                                "created_at_utc": "2026-03-27T19:20:01+00:00",
                                "updated_at_utc": "2026-03-27T21:51:15+00:00",
                            },
                            "native_newer": {
                                "source": "native_training",
                                "artifact_path": str(newer_artifact),
                                "is_active": True,
                                "is_preferred": False,
                                "validation_stage": "eligible",
                                "created_at_utc": "2026-03-27T22:00:14+00:00",
                                "updated_at_utc": "2026-03-27T22:05:45+00:00",
                            },
                        }
                    },
                    "datasets": {},
                },
            )
            settings = self._settings(registry_path)
            with patch(
                "Learning.runtime.resolve_model.build_family",
                return_value=_Family(family_hash),
            ):
                resolved = resolve_model(settings)

        self.assertTrue(resolved["found"])
        self.assertEqual(resolved["model_id"], "native_newer")
        self.assertEqual(Path(resolved["artifact_path"]), newer_artifact)

    def test_eligible_promotion_prefers_new_model_and_deactivates_peers(self) -> None:
        family_hash = "family-hash"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            older_artifact = root / "older.joblib"
            newer_artifact = root / "newer.joblib"
            older_artifact.write_bytes(b"old")
            newer_artifact.write_bytes(b"new")
            registry_path = self._write_registry(
                root,
                {
                    "families": {family_hash: {}},
                    "models": {
                        family_hash: {
                            "native_older": {
                                "source": "native_training",
                                "artifact_path": str(older_artifact),
                                "is_active": True,
                                "is_preferred": False,
                                "validation_stage": "eligible",
                                "created_at_utc": "2026-03-27T19:20:01+00:00",
                                "updated_at_utc": "2026-03-27T21:51:15+00:00",
                            },
                            "native_newer": {
                                "source": "native_training",
                                "artifact_path": str(newer_artifact),
                                "is_active": True,
                                "is_preferred": False,
                                "validation_stage": "candidate",
                                "created_at_utc": "2026-03-27T22:00:14+00:00",
                                "updated_at_utc": "2026-03-27T22:00:14+00:00",
                            },
                        }
                    },
                    "datasets": {},
                },
            )
            settings = self._settings(registry_path)

            # Mirror the train_surrogate gate-pass contract: eligible native
            # models become preferred and remove older active native peers.
            update_model_status(
                settings,
                family_hash,
                "native_newer",
                validation_stage="eligible",
                is_active=True,
                is_preferred=True,
            )

            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            family_entry = registry["families"][family_hash]
            older = registry["models"][family_hash]["native_older"]
            newer = registry["models"][family_hash]["native_newer"]

            self.assertEqual(family_entry["preferred_model_id"], "native_newer")
            self.assertTrue(newer["is_preferred"])
            self.assertTrue(newer["is_active"])
            self.assertEqual(newer["validation_stage"], "eligible")
            self.assertFalse(older["is_active"])
            self.assertFalse(older["is_preferred"])

            with patch(
                "Learning.runtime.resolve_model.build_family",
                return_value=_Family(family_hash),
            ):
                resolved = resolve_model(settings)

        self.assertTrue(resolved["found"])
        self.assertEqual(resolved["model_id"], "native_newer")

    def test_missing_preferred_artifact_falls_through_to_newest_active(self) -> None:
        family_hash = "family-hash"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fallback_artifact = root / "fallback.joblib"
            fallback_artifact.write_bytes(b"ok")
            registry_path = self._write_registry(
                root,
                {
                    "families": {
                        family_hash: {
                            "preferred_model_id": "native_missing",
                        }
                    },
                    "models": {
                        family_hash: {
                            "native_missing": {
                                "source": "native_training",
                                "artifact_path": str(root / "missing.joblib"),
                                "is_active": True,
                                "is_preferred": True,
                                "validation_stage": "eligible",
                                "created_at_utc": "2026-03-27T22:10:00+00:00",
                                "updated_at_utc": "2026-03-27T22:10:00+00:00",
                            },
                            "native_fallback": {
                                "source": "native_training",
                                "artifact_path": str(fallback_artifact),
                                "is_active": True,
                                "is_preferred": False,
                                "validation_stage": "eligible",
                                "created_at_utc": "2026-03-27T19:20:01+00:00",
                                "updated_at_utc": "2026-03-27T21:51:15+00:00",
                            },
                        }
                    },
                    "datasets": {},
                },
            )
            settings = self._settings(registry_path)
            with patch(
                "Learning.runtime.resolve_model.build_family",
                return_value=_Family(family_hash),
            ):
                resolved = resolve_model(settings)

        self.assertTrue(resolved["found"])
        self.assertEqual(resolved["model_id"], "native_fallback")


if __name__ == "__main__":
    unittest.main()
