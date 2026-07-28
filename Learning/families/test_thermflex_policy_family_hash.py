"""Family hash must separate constant ThermFlex lower-bound policies."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from Learning.families.build_family import build_family


def _settings(*, constant_lower_bound_c, constrain_upper_temperature: bool = False):
    return SimpleNamespace(
        engine=SimpleNamespace(system_id="integrated_energy_system"),
        run=SimpleNamespace(tag="test"),
        surrogate=SimpleNamespace(model="rf"),
        surrogate_train=SimpleNamespace(
            model_params={},
            targets=["dispatch_operating_cost_eur"],
            target_profile="dispatch_optimization_core",
            target_profiles={
                "dispatch_optimization_core": ["dispatch_operating_cost_eur"],
            },
            append_active_technology_targets=False,
            include_objectives=False,
            feature_names=[],
            feature_encoding={},
        ),
        market=SimpleNamespace(active_tariff_arm="flat"),
        learning=SimpleNamespace(
            dispatch_model_id="default",
            resolution="1h",
            horizon_type="full_year",
            time_series_schema=[],
            location_mode="dataset_context",
        ),
        bounds=SimpleNamespace(names=["pv_kwp"], steps=[1.0], caps={}),
        objectives=SimpleNamespace(names=["dispatch_operating_cost_eur"], minimize=[True]),
        constraints=SimpleNamespace(
            thermflex=SimpleNamespace(
                use_explicit_lower_bounds=True,
                constant_lower_bound_c=constant_lower_bound_c,
                day_lower_bound_c=None,
                night_lower_bound_c=None,
                constrain_upper_temperature=constrain_upper_temperature,
                max_flex_duration_h=24,
                max_flex_events_per_day=24,
            )
        ),
    )


class FamilyThermflexPolicyIdentityTests(unittest.TestCase):
    def test_constant_lower_bound_changes_family_hash(self):
        lb21 = build_family(_settings(constant_lower_bound_c=21.0))
        lb22 = build_family(
            _settings(constant_lower_bound_c=22.5, constrain_upper_temperature=True)
        )
        self.assertNotEqual(lb21.family_hash, lb22.family_hash)
        self.assertEqual(lb21.dispatch_signature["dispatch_params"]["constant_lower_bound_c"], 21.0)
        self.assertEqual(lb22.dispatch_signature["dispatch_params"]["constant_lower_bound_c"], 22.5)


if __name__ == "__main__":
    unittest.main()
