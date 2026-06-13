from __future__ import annotations

import importlib.util
import unittest

if importlib.util.find_spec("pandas") is None:
    raise unittest.SkipTest("pandas is required for thermflex_daily_results.predict")

from Learning.thermflex_daily_results.predict import (
    _resolve_model_feature_mode,
    _template_required_columns,
)
from Learning.thermflex_daily_results.schema import (
    DISPATCH_ECONOMICS_ENGINEERED_FEATURE_COLUMNS,
    DISPATCH_ECONOMICS_REFERENCE_FEATURE_COLUMNS,
    DISPATCH_STATE_ENGINEERED_FEATURE_COLUMNS,
    DISPATCH_STATE_REFERENCE_FEATURE_COLUMNS,
)


class PredictFeatureModeTest(unittest.TestCase):
    def test_resolves_explicit_feature_mode_from_model_bundle(self) -> None:
        self.assertEqual(
            _resolve_model_feature_mode(
                model_bundle={
                    "feature_mode": "dispatch_economics_stateful",
                    "feature_columns": ["date"],
                },
                meta={},
            ),
            "dispatch_economics_stateful",
        )

    def test_infers_dispatch_economics_from_legacy_feature_columns(self) -> None:
        self.assertEqual(
            _resolve_model_feature_mode(
                model_bundle={
                    "feature_columns": [
                        "date",
                        DISPATCH_ECONOMICS_ENGINEERED_FEATURE_COLUMNS[0],
                    ],
                },
                meta={},
            ),
            "dispatch_economics",
        )

    def test_infers_stateful_mode_from_legacy_feature_columns(self) -> None:
        self.assertEqual(
            _resolve_model_feature_mode(
                model_bundle={
                    "feature_columns": [
                        "date",
                        DISPATCH_STATE_ENGINEERED_FEATURE_COLUMNS[0],
                    ],
                },
                meta={},
            ),
            "dispatch_economics_stateful",
        )

    def test_template_columns_include_dispatch_contract_columns(self) -> None:
        economics_columns = _template_required_columns(feature_mode="dispatch_economics")
        stateful_columns = _template_required_columns(feature_mode="dispatch_economics_stateful")

        self.assertIn(DISPATCH_ECONOMICS_REFERENCE_FEATURE_COLUMNS[0], economics_columns)
        self.assertIn(DISPATCH_ECONOMICS_REFERENCE_FEATURE_COLUMNS[0], stateful_columns)
        self.assertIn(DISPATCH_STATE_REFERENCE_FEATURE_COLUMNS[0], stateful_columns)
        self.assertNotIn(DISPATCH_STATE_REFERENCE_FEATURE_COLUMNS[0], economics_columns)


if __name__ == "__main__":
    unittest.main()
