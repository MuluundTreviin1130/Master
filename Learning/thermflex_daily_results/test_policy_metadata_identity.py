"""Focused tests for curated ThermFlex policy identity descriptors."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from Learning.thermflex_daily_results.policy_identity import policy_metadata_from_settings


def _settings(
    *,
    setpoint_c: float = 22.5,
    lower_bound_c: float | None = 22.5,
    use_explicit_lower_bounds: bool = True,
    constrain_upper_temperature: bool = True,
    max_flex_duration_h: int = 24,
    max_flex_events_per_day: int = 24,
    dh_bus_inertia_tau_h: float = 4.0,
    horizon_h: int = 24,
    rolling_commit_h: int = 24,
) -> SimpleNamespace:
    """Build a minimal settings stub that matches the descriptor contract."""

    return SimpleNamespace(
        heating_control=SimpleNamespace(constant_setpoint_c=setpoint_c),
        constraints=SimpleNamespace(
            thermflex=SimpleNamespace(
                use_explicit_lower_bounds=use_explicit_lower_bounds,
                constant_lower_bound_c=lower_bound_c,
                constrain_upper_temperature=constrain_upper_temperature,
                max_flex_duration_h=max_flex_duration_h,
                max_flex_events_per_day=max_flex_events_per_day,
            )
        ),
        dispatch=SimpleNamespace(
            dh_bus_inertia_tau_h=dh_bus_inertia_tau_h,
            horizon_h=horizon_h,
            rolling_commit_h=rolling_commit_h,
        ),
    )


class PolicyMetadataIdentityTests(unittest.TestCase):
    def test_constrain_upper_flag_distinguishes_otherwise_identical_upper_only_policies(self) -> None:
        """Paper upper-only twins that differ only by the upper comfort flag must not collide."""

        constrained = policy_metadata_from_settings(
            settings=_settings(constrain_upper_temperature=True),
            context_label="upper constrained",
        )
        unconstrained = policy_metadata_from_settings(
            settings=_settings(constrain_upper_temperature=False),
            context_label="upper unconstrained",
        )

        # Legacy descriptors still collapse both cases onto UPPER_24H / upper_only.
        self.assertEqual(constrained["policy_case_label_canonical"], "UPPER_24H")
        self.assertEqual(unconstrained["policy_case_label_canonical"], "UPPER_24H")
        self.assertTrue(constrained["policy_upper_only"])
        self.assertTrue(unconstrained["policy_upper_only"])
        self.assertEqual(
            constrained["policy_lower_relaxation_k"],
            unconstrained["policy_lower_relaxation_k"],
        )

        # The live envelope flag is the identity that prevents silent feature collision.
        self.assertEqual(constrained["policy_constrain_upper_temperature"], 1.0)
        self.assertEqual(unconstrained["policy_constrain_upper_temperature"], 0.0)

    def test_use_explicit_lower_bounds_flag_is_encoded(self) -> None:
        explicit = policy_metadata_from_settings(
            settings=_settings(use_explicit_lower_bounds=True, lower_bound_c=22.5),
            context_label="explicit lower",
        )
        inactive = policy_metadata_from_settings(
            settings=_settings(use_explicit_lower_bounds=False, lower_bound_c=None),
            context_label="inactive lower",
        )
        self.assertEqual(explicit["policy_use_explicit_lower_bounds"], 1.0)
        self.assertEqual(inactive["policy_use_explicit_lower_bounds"], 0.0)
        # Inactive explicit lowers must not invent a distinct relaxation identity.
        self.assertEqual(inactive["policy_constant_lower_bound_c"], 22.5)
        self.assertEqual(inactive["policy_lower_relaxation_k"], 0.0)

    def test_explicit_lower_requires_constant_lower_bound(self) -> None:
        with self.assertRaisesRegex(ValueError, "constant_lower_bound_c"):
            policy_metadata_from_settings(
                settings=_settings(use_explicit_lower_bounds=True, lower_bound_c=None),
                context_label="missing lower",
            )


if __name__ == "__main__":
    unittest.main()
