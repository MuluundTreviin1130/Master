from __future__ import annotations

import ast
import importlib.util
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
RUN_OPTIMIZATION = ROOT / "Optimization" / "run" / "runners" / "run_optimization.py"
TRAIN_SURROGATE = ROOT / "Optimization" / "run" / "runners" / "train_surrogate.py"
PAPER_SURROGATE_RUNNER = (
    ROOT / "Optimization" / "run" / "papers" / "dh_thermflex" / "train_vienna_thermflex_surrogates.py"
)


def _install_stub_module(originals: dict[str, types.ModuleType | None], name: str, **attrs) -> None:
    parts = name.split(".")
    for idx in range(1, len(parts) + 1):
        module_name = ".".join(parts[:idx])
        if module_name not in originals:
            originals[module_name] = sys.modules.get(module_name)
        if module_name not in sys.modules:
            module = types.ModuleType(module_name)
            module.__path__ = []
            sys.modules[module_name] = module
        if idx > 1:
            parent_name = ".".join(parts[: idx - 1])
            setattr(sys.modules[parent_name], parts[idx - 1], sys.modules[module_name])

    module = sys.modules[name]
    for attr_name, attr_value in attrs.items():
        setattr(module, attr_name, attr_value)


def _load_module_with_stubs(path: Path, module_name: str, stubs: dict[str, dict[str, object]]):
    originals: dict[str, types.ModuleType | None] = {}
    try:
        for stub_name, attrs in stubs.items():
            _install_stub_module(originals, stub_name, **attrs)

        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"could not load module spec for {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for stub_name, original in reversed(list(originals.items())):
            if original is None:
                sys.modules.pop(stub_name, None)
            else:
                sys.modules[stub_name] = original


class RunnerRegressionTests(unittest.TestCase):
    def test_gitignore_allows_optimization_validation_ssot(self) -> None:
        candidate = (
            "Optimization/validation/model_validation/overrides/thermflex/"
            "vienna_ref2023_dh_day_night_thermflex_two_stage.json"
        )

        result = subprocess.run(["git", "check-ignore", "-q", candidate], cwd=ROOT)

        self.assertEqual(
            result.returncode,
            1,
            "Optimization/validation is an SSOT input layer and must not be hidden by .gitignore.",
        )

    def test_click_run_default_fails_fast_when_missing_ssot_override(self) -> None:
        module = _load_module_with_stubs(
            RUN_OPTIMIZATION,
            "_run_optimization_under_test",
            {
                "Settings": {"get_settings": lambda overrides=None: None},
                "Optimization.framework.Orchestrator.optimize": {"run": lambda settings: {}},
                "Optimization.framework.scheduler.successive_halving": {
                    "run_scheduler": lambda base_overrides=None: {}
                },
                "Optimization.run.analysis.run_metrics": {"write_run_metrics": lambda *args, **kwargs: None},
            },
        )

        with patch.object(sys, "argv", [str(RUN_OPTIMIZATION)]):
            with self.assertRaises(FileNotFoundError) as ctx:
                module._load_json(None)

        self.assertIn("click-run default overrides file not found", str(ctx.exception))

    def test_click_train_default_fails_fast_when_missing_ssot_override(self) -> None:
        module = _load_module_with_stubs(
            TRAIN_SURROGATE,
            "_train_surrogate_under_test",
            {
                "Settings": {"get_settings": lambda overrides=None: None},
                "Optimization.framework.engines.Surrogat_model.features": {
                    "build_signature_context_payload": lambda settings, profile_id: {},
                    "build_signature_system_flags": lambda settings, params_base: {},
                    "resolve_feature_encoding": lambda settings: {},
                    "resolve_feature_names": lambda settings: [],
                    "resolve_surrogate_family": lambda settings: "stub_family",
                    "resolve_surrogate_targets": lambda settings: ["stub_target"],
                },
                "Optimization.framework.engines.Surrogat_model.training": {
                    "auto_train_surrogate": lambda settings: "stub/model.json"
                },
                "Optimization.framework.engines.signature_utils": {
                    "build_signature_dict": lambda *args, **kwargs: {},
                    "signature_hash": lambda payload: "stub_hash",
                },
                "Optimization.framework.engines.profiles_meta": {
                    "get_profile_id": lambda profiles, settings: "stub_profile"
                },
                "Optimization.framework.engines.Gated.io": {
                    "promote_surrogate_version": lambda *args, **kwargs: None
                },
                "Technical_model.energy_system.precompute.adapter": {
                    "prepare_profiles_adapter": lambda settings: types.SimpleNamespace(profiles={}, params_base={})
                },
            },
        )

        with patch.object(sys, "argv", [str(TRAIN_SURROGATE)]):
            with self.assertRaises(FileNotFoundError) as ctx:
                module._load_overrides(None)

        self.assertIn("click-train default overrides file not found", str(ctx.exception))

    def test_paper_surrogate_runner_uses_existing_signature_helper_module(self) -> None:
        tree = ast.parse(PAPER_SURROGATE_RUNNER.read_text(encoding="utf-8"))
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
            if alias.name == "_build_signature_hash"
        }

        self.assertIn("Optimization.run.runners.train_surrogate", imports)
        self.assertNotIn("Optimization.run.train_surrogate", imports)


if __name__ == "__main__":
    unittest.main()
