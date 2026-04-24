from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List


def _require_float(container: Dict[str, Any], key: str, ctx: str) -> float:
    if key not in container:
        raise ValueError(f"[replacements] Missing required key '{key}' in {ctx}.")
    return float(container[key])


def _require_positive(value: float, name: str) -> float:
    if value <= 0.0:
        raise ValueError(f"[replacements] '{name}' must be > 0, got {value}.")
    return value


@dataclass(frozen=True)
class ReplacementInfo:
    tech: str
    interval_years: float
    n_total_units: float
    replacement_years: List[float]

    @property
    def n_replacements_continuous(self) -> float:
        return max(0.0, float(self.n_total_units) - 1.0)

    @property
    def n_replacements_discrete(self) -> int:
        return len(self.replacement_years)


def _replacement_years(lifetime_years: float, interval_years: float) -> List[float]:
    years: List[float] = []
    k = 1
    while True:
        y = float(k) * float(interval_years)
        if y >= float(lifetime_years):
            break
        years.append(y)
        k += 1
    return years


def compute_pv_replacement(params: Dict[str, Any]) -> ReplacementInfo:
    life = float(_require_positive(_require_float(params, "lifetime", "params"), "params.lifetime"))
    pv = params.get("PV")
    if not isinstance(pv, dict):
        raise ValueError("[replacements] Missing required dict params['PV'].")
    pv_life = float(_require_positive(_require_float(pv, "lifetime_years", "params['PV']"), "params['PV'].lifetime_years"))
    interval = pv_life
    return ReplacementInfo(
        tech="PV",
        interval_years=interval,
        n_total_units=life / interval,
        replacement_years=_replacement_years(life, interval),
    )


def compute_fc_replacement(
    params: Dict[str, Any],
    *,
    fc_kw: float,
    annual_fc_output_kwh: float = 0.0,
) -> ReplacementInfo:
    life = float(_require_positive(_require_float(params, "lifetime", "params"), "params.lifetime"))
    fc = params.get("FC")
    if not isinstance(fc, dict):
        raise ValueError("[replacements] Missing required dict params['FC'].")

    cal_life = float(_require_positive(_require_float(fc, "lifetime_years", "params['FC']"), "params['FC'].lifetime_years"))
    hours_life = float(_require_positive(_require_float(fc, "lifetime_hours", "params['FC']"), "params['FC'].lifetime_hours"))

    if fc_kw < 0.0:
        raise ValueError(f"[replacements] fc_kw must be >= 0, got {fc_kw}.")
    if annual_fc_output_kwh < 0.0:
        raise ValueError(f"[replacements] annual_fc_output_kwh must be >= 0, got {annual_fc_output_kwh}.")

    usage_interval = math.inf
    if fc_kw > 0.0 and annual_fc_output_kwh > 0.0:
        yearly_full_load_hours = annual_fc_output_kwh / fc_kw
        if yearly_full_load_hours > 0.0:
            usage_interval = hours_life / yearly_full_load_hours

    interval = min(cal_life, usage_interval)
    if not math.isfinite(interval) or interval <= 0.0:
        interval = cal_life

    return ReplacementInfo(
        tech="FC",
        interval_years=interval,
        n_total_units=life / interval,
        replacement_years=_replacement_years(life, interval),
    )


def compute_bess_replacement(
    params: Dict[str, Any],
    *,
    bess_kwh: float,
    annual_bess_throughput_kwh: float = 0.0,
) -> ReplacementInfo:
    life = float(_require_positive(_require_float(params, "lifetime", "params"), "params.lifetime"))
    bs = params.get("BESS")
    if not isinstance(bs, dict):
        raise ValueError("[replacements] Missing required dict params['BESS'].")

    cal_life = float(_require_positive(_require_float(bs, "battery_lifetime", "params['BESS']"), "params['BESS'].battery_lifetime"))
    max_cycles = float(_require_positive(_require_float(bs, "max_cycles", "params['BESS']"), "params['BESS'].max_cycles"))
    dod = float(_require_positive(_require_float(bs, "DoD", "params['BESS']"), "params['BESS'].DoD"))

    if bess_kwh < 0.0:
        raise ValueError(f"[replacements] bess_kwh must be >= 0, got {bess_kwh}.")
    if annual_bess_throughput_kwh < 0.0:
        raise ValueError(f"[replacements] annual_bess_throughput_kwh must be >= 0, got {annual_bess_throughput_kwh}.")

    usage_interval = math.inf
    if bess_kwh > 0.0 and annual_bess_throughput_kwh > 0.0:
        # Throughput in this repo is charge+discharge energy.
        cycle_lifetime_throughput = 2.0 * bess_kwh * dod * max_cycles
        usage_interval = cycle_lifetime_throughput / annual_bess_throughput_kwh

    interval = min(cal_life, usage_interval)
    if not math.isfinite(interval) or interval <= 0.0:
        interval = cal_life

    return ReplacementInfo(
        tech="BESS",
        interval_years=interval,
        n_total_units=life / interval,
        replacement_years=_replacement_years(life, interval),
    )
