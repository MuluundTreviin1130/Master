from __future__ import annotations

"""Scheduler arms for SH/Hyperband meta-runs.

Arms are plain dictionaries on purpose so they can be consumed by the
scheduler without creating import cycles with SchedulerArmConfig.

An arm may optionally define ``tariff_arm``. If omitted, the run uses the
active tariff from ``settings.market.active_tariff_arm``.
"""


def _classic_features(b: int, v: int, h: int, t: int) -> dict:
    return {
        "enable_bess": bool(b),
        "enable_v2h": bool(v),
        "enable_h2": bool(h),
        "enable_thermflex": bool(t),
    }


def _apply_classic_overrides(arm: dict, h: int, t: int) -> None:
    if bool(h):
        arm["caps_override"] = {
            "per_ec_ely_kw": 10.0,
            "per_ec_h2_tank_kwh": 100.0,
            "per_ec_fc_kw": 10.0,
        }
    if bool(t):
        arm["delta_t_override"] = 2.0


def make_default_arms() -> list[dict]:
    """Return the baseline technology arms used by the scheduler.

    The current defaults intentionally stay technology-only so existing SH runs
    remain unchanged. Tariff-aware scheduler runs can add ``tariff_arm`` to any
    individual arm dictionary without needing a second arm-generation path.
    """

    arms: list[dict] = []
    for b in (0, 1):
        for v in (0, 1):
            for h in (0, 1):
                for t in (0, 1):
                    features = _classic_features(b, v, h, t)
                    arm: dict = {
                        "name": f"bess{b}_v2h{v}_h2{h}_tf{t}",
                        "features": features,
                    }
                    _apply_classic_overrides(arm, h, t)
                    arms.append(arm)
    return arms


def make_giw_arms() -> list[dict]:
    """Return the expanded GIW arm space.

    Dimensions:
    - classic portfolio toggles: BESS, V2H, H2, ThermFlex
    - wind option: none / small / large (mutually exclusive)
    - wood gasifier: off / on
    - tariff regime: flat / tou / dynamic / export_penalty

    The generator intentionally leaves biogas disabled for now because the
    current GIW paper direction focuses on tariff-aware screening with wind and
    wood gasifier extensions.
    """

    tariff_arms = ("flat", "tou", "dynamic", "export_penalty")
    wind_options = (
        ("wind0", False, False),
        ("sw1", True, False),
        ("lw1", False, True),
    )

    arms: list[dict] = []
    for tariff_arm in tariff_arms:
        for b in (0, 1):
            for v in (0, 1):
                for h in (0, 1):
                    for t in (0, 1):
                        for wind_tag, enable_small_wind, enable_large_wind in wind_options:
                            for wood in (0, 1):
                                features = _classic_features(b, v, h, t)
                                features.update(
                                    {
                                        "enable_small_wind": bool(enable_small_wind),
                                        "enable_large_wind": bool(enable_large_wind),
                                        "enable_biogas_engine": False,
                                        "enable_wood_gasifier": bool(wood),
                                    }
                                )
                                arm: dict = {
                                    "name": (
                                        f"tariff_{tariff_arm}_"
                                        f"bess{b}_v2h{v}_h2{h}_tf{t}_"
                                        f"{wind_tag}_wg{wood}"
                                    ),
                                    "features": features,
                                    "tariff_arm": tariff_arm,
                                }
                                _apply_classic_overrides(arm, h, t)
                                arms.append(arm)
    return arms


def make_scheduler_arms(mode: str = "baseline") -> list[dict]:
    mode_norm = str(mode or "baseline").strip().lower()
    if mode_norm == "giw":
        return make_giw_arms()
    return make_default_arms()
