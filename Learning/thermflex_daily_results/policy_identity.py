"""Import-light ThermFlex policy descriptors for curated daily/hourly learning."""

from __future__ import annotations

from typing import Any


def policy_metadata_from_settings(*, settings: Any, context_label: str) -> dict[str, Any]:
    """
    Build curated ThermFlex policy descriptors from live settings.

    Constant-mode paper policies can differ only by
    `constrain_upper_temperature` and/or `use_explicit_lower_bounds` while
    sharing the same setpoint, lower relaxation, duration, and event budget.
    Those flags change MILP teacher labels, so they must be explicit numeric
    features for daily_results / hourly_dispatch train and predict paths.
    """

    thermflex_cfg = settings.constraints.thermflex
    dispatch_cfg = settings.dispatch
    heating_cfg = settings.heating_control
    if not hasattr(heating_cfg, "constant_setpoint_c"):
        raise AttributeError(
            "[thermflex_daily_results] required heating_control setting "
            f"`constant_setpoint_c` missing in {context_label}."
        )
    setpoint_raw = getattr(heating_cfg, "constant_setpoint_c")
    if setpoint_raw is None:
        raise ValueError(
            "[thermflex_daily_results] required heating_control setting "
            f"`constant_setpoint_c` is None in {context_label}."
        )
    setpoint_c = float(setpoint_raw)
    use_explicit_lower_bounds = bool(getattr(thermflex_cfg, "use_explicit_lower_bounds", False))
    constrain_upper_temperature = bool(getattr(thermflex_cfg, "constrain_upper_temperature", False))
    # Explicit lowers are optional in Settings. When activated they are required;
    # when inactive, do not invent a distinct relaxation identity from Optional None
    # or from an unused declared lower that MILP ignores.
    if use_explicit_lower_bounds:
        raw_lower = getattr(thermflex_cfg, "constant_lower_bound_c", None)
        if raw_lower is None:
            raise ValueError(
                "[thermflex_daily_results] use_explicit_lower_bounds=True requires "
                f"constraints.thermflex.constant_lower_bound_c in {context_label}."
            )
        lower_bound_c = float(raw_lower)
    else:
        lower_bound_c = float(setpoint_c)
    lower_relaxation_k = float(setpoint_c - lower_bound_c)
    duration_h = float(getattr(thermflex_cfg, "max_flex_duration_h"))
    max_events_per_day = float(getattr(thermflex_cfg, "max_flex_events_per_day"))
    dispatch_contract = dispatch_solve_contract(
        dispatch_cfg=dispatch_cfg,
        context_label=f"dispatch settings for {context_label}",
    )
    return {
        "policy_case_label_canonical": build_canonical_case_label(
            duration_h=duration_h,
            lower_relaxation_k=lower_relaxation_k,
            max_events_per_day=max_events_per_day,
        ),
        "policy_duration_h": duration_h,
        "policy_max_events_per_day": max_events_per_day,
        "policy_constant_lower_bound_c": lower_bound_c,
        "policy_lower_relaxation_k": lower_relaxation_k,
        "policy_tau_h": float(getattr(dispatch_cfg, "dh_bus_inertia_tau_h")),
        **dispatch_contract,
        "policy_upper_only": bool(abs(lower_relaxation_k) < 1e-12),
        # Live comfort envelope flags: sibling of native surrogate ThermFlex identity.
        "policy_use_explicit_lower_bounds": float(int(use_explicit_lower_bounds)),
        "policy_constrain_upper_temperature": float(int(constrain_upper_temperature)),
    }


def dispatch_solve_contract(*, dispatch_cfg: Any, context_label: str) -> dict[str, float]:
    """Expose the MILP rolling-horizon contract as stable learning features."""

    horizon_h = required_positive_int_attr(
        dispatch_cfg,
        "horizon_h",
        context_label=context_label,
    )
    rolling_commit_raw_h = required_nonnegative_int_attr(
        dispatch_cfg,
        "rolling_commit_h",
        context_label=context_label,
    )
    rolling_commit_h = horizon_h if rolling_commit_raw_h <= 0 else rolling_commit_raw_h
    if rolling_commit_h > horizon_h:
        raise ValueError(
            "[thermflex_daily_results] dispatch rolling horizon contract invalid in "
            f"{context_label}: rolling_commit_h={rolling_commit_h}, horizon_h={horizon_h}."
        )
    lookahead_h = horizon_h - rolling_commit_h
    return {
        "policy_dispatch_horizon_h": float(horizon_h),
        "policy_dispatch_rolling_commit_h": float(rolling_commit_h),
        "policy_dispatch_lookahead_h": float(lookahead_h),
        "policy_dispatch_is_rolling": float(lookahead_h > 0),
    }


def required_positive_int_attr(obj: Any, attr_name: str, *, context_label: str) -> int:
    value = required_int_attr(obj, attr_name, context_label=context_label)
    if value <= 0:
        raise ValueError(
            "[thermflex_daily_results] required positive integer setting "
            f"`{attr_name}` must be > 0 in {context_label}, got {value}."
        )
    return value


def required_nonnegative_int_attr(obj: Any, attr_name: str, *, context_label: str) -> int:
    value = required_int_attr(obj, attr_name, context_label=context_label)
    if value < 0:
        raise ValueError(
            "[thermflex_daily_results] required nonnegative integer setting "
            f"`{attr_name}` must be >= 0 in {context_label}, got {value}."
        )
    return value


def required_int_attr(obj: Any, attr_name: str, *, context_label: str) -> int:
    if not hasattr(obj, attr_name):
        raise AttributeError(
            "[thermflex_daily_results] required dispatch setting "
            f"`{attr_name}` missing in {context_label}."
        )
    value = getattr(obj, attr_name)
    if value is None:
        raise ValueError(
            "[thermflex_daily_results] required dispatch setting "
            f"`{attr_name}` is None in {context_label}."
        )
    return int(value)


def build_canonical_case_label(
    *,
    duration_h: float,
    lower_relaxation_k: float,
    max_events_per_day: float,
) -> str:
    """Create one canonical case label directly from policy parameters."""

    if abs(lower_relaxation_k) < 1e-12:
        return f"UPPER_{int(round(duration_h))}H"
    lower_label = str(int(round(lower_relaxation_k)))
    return f"LOWER{lower_label}K_DUR{int(round(duration_h))}_EVT{int(round(max_events_per_day))}"
