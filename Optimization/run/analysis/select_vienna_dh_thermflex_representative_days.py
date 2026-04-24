from __future__ import annotations

"""Select representative Vienna DH thermflex analysis days from 2023 inputs."""

import json
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg", force=True)
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from Optimization.run.analysis.dh_thermflex_inputs import (
    load_vienna_dh_thermflex_full_year_context,
)


def build_vienna_dh_thermflex_representative_days_bundle(output_dir: Path) -> Path:
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    context = load_vienna_dh_thermflex_full_year_context()
    daily = _build_daily_features(context)
    daily.to_csv(output_dir / "representative_day_features.csv", index=True)

    selected = _select_representative_days(daily)
    payload = {
        "selection_method": "explicit_rule_based_medoid_selector_v1",
        "source_override_path": str(context.source_override_path),
        "selected_days": selected,
    }
    (output_dir / "representative_days.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_markdown(output_dir=output_dir, selected=selected)
    _save_plot(output_dir=output_dir, daily=daily, selected=selected)
    return output_dir


def _build_daily_features(context) -> pd.DataFrame:
    hourly = context.hourly_system_df.copy()
    hourly["timestamp"] = pd.to_datetime(hourly["timestamp"])
    hourly = hourly.set_index("timestamp")

    daily = hourly.resample("D").agg(
        {
            "dh_space_heat_total_kwh": "sum",
            "dh_hotwater_total_kwh": "sum",
            "dh_total_kwh": "sum",
            "electric_load_total_kwh": "sum",
            "t_outdoor_c": ["mean", "min", "max"],
            "irradiance_proxy": "sum",
            "solargains_proxy": "sum",
            "mc_auction_eur_mwh": ["mean", "max"],
            "gas_price_eur_mwh_fuel": "mean",
            "co2_price_eur_tco2": "mean",
        }
    )
    daily.columns = _flatten_columns(daily.columns)
    daily = daily.rename(
        columns={
            "dh_space_heat_total_kwh_sum": "dh_space_heat_total_kwh",
            "dh_hotwater_total_kwh_sum": "dh_hotwater_total_kwh",
            "dh_total_kwh_sum": "dh_total_kwh",
            "electric_load_total_kwh_sum": "electric_load_total_kwh",
            "irradiance_proxy_sum": "irradiance_proxy_sum",
            "solargains_proxy_sum": "solargains_proxy_sum",
            "t_outdoor_c_mean": "t_outdoor_mean_c",
            "t_outdoor_c_min": "t_outdoor_min_c",
            "t_outdoor_c_max": "t_outdoor_max_c",
            "mc_auction_eur_mwh_mean": "mc_auction_mean_eur_mwh",
            "mc_auction_eur_mwh_max": "mc_auction_peak_eur_mwh",
            "gas_price_eur_mwh_fuel_mean": "gas_price_mean_eur_mwh_fuel",
            "co2_price_eur_tco2_mean": "co2_price_mean_eur_tco2",
        }
    )
    daily.index.name = "date"
    daily["month"] = daily.index.month.astype(int)
    daily["is_heating_day"] = daily["dh_space_heat_total_kwh"] > 1e-6
    daily["is_winter_day"] = daily["month"].isin([12, 1, 2])
    daily["is_shoulder_day"] = daily["month"].isin([3, 4, 10, 11])
    daily["hdd18_kh"] = np.maximum(0.0, 18.0 - daily["t_outdoor_mean_c"]) * 24.0
    return daily


def _select_representative_days(daily: pd.DataFrame) -> list[dict[str, object]]:
    selected_dates: set[pd.Timestamp] = set()
    selections: list[dict[str, object]] = []

    winter_heating = daily[daily["is_heating_day"] & daily["is_winter_day"]].copy()
    if winter_heating.empty:
        raise ValueError("[representative_days] No winter heating days available for selection.")
    shoulder_heating = daily[daily["is_heating_day"] & daily["is_shoulder_day"]].copy()
    if shoulder_heating.empty:
        raise ValueError("[representative_days] No shoulder heating days available for selection.")

    selections.append(
        _select_ranked_day(
            label="winter_peak_heat_day",
            rationale="Highest winter DH space-heat day in the model-side 2023 input year.",
            ranked_days=winter_heating.sort_values("dh_space_heat_total_kwh", ascending=False),
            selected_dates=selected_dates,
        )
    )
    selections.append(
        _select_ranked_day(
            label="winter_price_spike_day",
            rationale="Highest winter day-ahead price day among winter heating days.",
            ranked_days=winter_heating.sort_values("mc_auction_mean_eur_mwh", ascending=False),
            selected_dates=selected_dates,
        )
    )

    winter_sunny_pool = winter_heating[
        winter_heating["dh_space_heat_total_kwh"] >= winter_heating["dh_space_heat_total_kwh"].median()
    ].copy()
    if winter_sunny_pool.empty:
        raise ValueError("[representative_days] Winter sunny pool is empty after median-heat filter.")
    selections.append(
        _select_ranked_day(
            label="winter_sunny_heat_day",
            rationale="Sunny winter heating day with above-median winter DH heat demand.",
            ranked_days=winter_sunny_pool.sort_values("solargains_proxy_sum", ascending=False),
            selected_dates=selected_dates,
        )
    )

    winter_feature_cols = [
        "dh_space_heat_total_kwh",
        "t_outdoor_mean_c",
        "t_outdoor_min_c",
        "solargains_proxy_sum",
        "mc_auction_mean_eur_mwh",
        "co2_price_mean_eur_tco2",
    ]
    selections.append(
        _select_medoid_like_day(
            label="winter_typical_day",
            rationale="Winter heating day closest to the winter median feature vector.",
            candidates=winter_heating,
            feature_cols=winter_feature_cols,
            selected_dates=selected_dates,
        )
    )

    shoulder_feature_cols = [
        "dh_space_heat_total_kwh",
        "t_outdoor_mean_c",
        "t_outdoor_min_c",
        "solargains_proxy_sum",
        "mc_auction_mean_eur_mwh",
    ]
    selections.append(
        _select_medoid_like_day(
            label="shoulder_typical_day",
            rationale="Shoulder-season heating day closest to the shoulder median feature vector.",
            candidates=shoulder_heating,
            feature_cols=shoulder_feature_cols,
            selected_dates=selected_dates,
        )
    )
    return selections


def _select_ranked_day(
    *,
    label: str,
    rationale: str,
    ranked_days: pd.DataFrame,
    selected_dates: set[pd.Timestamp],
) -> dict[str, object]:
    for date, row in ranked_days.iterrows():
        date = pd.Timestamp(date)
        if date in selected_dates:
            continue
        selected_dates.add(date)
        return _build_selected_payload(label=label, rationale=rationale, date=date, row=row)
    raise ValueError(f"[representative_days] No unique date left for selector '{label}'.")


def _select_medoid_like_day(
    *,
    label: str,
    rationale: str,
    candidates: pd.DataFrame,
    feature_cols: list[str],
    selected_dates: set[pd.Timestamp],
) -> dict[str, object]:
    missing = [col for col in feature_cols if col not in candidates.columns]
    if missing:
        raise KeyError(
            f"[representative_days] Missing feature columns for selector '{label}': {missing}"
        )
    feature_df = candidates[feature_cols].astype(float)
    center = feature_df.median(axis=0)
    scale = feature_df.std(axis=0).replace(0.0, 1.0)
    z = (feature_df - center) / scale
    distance = np.sqrt((z**2).sum(axis=1))
    ranked = candidates.assign(selection_distance=distance).sort_values(
        ["selection_distance", "dh_space_heat_total_kwh"]
    )
    for date, row in ranked.iterrows():
        date = pd.Timestamp(date)
        if date in selected_dates:
            continue
        selected_dates.add(date)
        payload = _build_selected_payload(label=label, rationale=rationale, date=date, row=row)
        payload["selection_distance"] = float(row["selection_distance"])
        return payload
    raise ValueError(f"[representative_days] No unique date left for selector '{label}'.")


def _build_selected_payload(
    *,
    label: str,
    rationale: str,
    date: pd.Timestamp,
    row: pd.Series,
) -> dict[str, object]:
    return {
        "label": label,
        "date": str(date.date()),
        "rationale": rationale,
        "dh_space_heat_total_gwh": float(row["dh_space_heat_total_kwh"]) / 1e6,
        "dh_hotwater_total_gwh": float(row["dh_hotwater_total_kwh"]) / 1e6,
        "dh_total_gwh": float(row["dh_total_kwh"]) / 1e6,
        "t_outdoor_mean_c": float(row["t_outdoor_mean_c"]),
        "t_outdoor_min_c": float(row["t_outdoor_min_c"]),
        "solargains_proxy_sum": float(row["solargains_proxy_sum"]),
        "mc_auction_mean_eur_mwh": float(row["mc_auction_mean_eur_mwh"]),
        "mc_auction_peak_eur_mwh": float(row["mc_auction_peak_eur_mwh"]),
        "gas_price_mean_eur_mwh_fuel": float(row["gas_price_mean_eur_mwh_fuel"]),
        "co2_price_mean_eur_tco2": float(row["co2_price_mean_eur_tco2"]),
    }


def _write_markdown(*, output_dir: Path, selected: list[dict[str, object]]) -> None:
    lines = [
        "# Vienna DH Thermflex Representative Days",
        "",
        "Selection method: explicit rule-based medoid selector on model-side 2023 daily features.",
        "",
    ]
    for item in selected:
        lines.extend(
            [
                f"## {item['label']}",
                "",
                f"- Date: `{item['date']}`",
                f"- Rationale: {item['rationale']}",
                f"- DH total: `{float(item['dh_total_gwh']):.3f} GWh/day`",
                f"- DH space heat: `{float(item['dh_space_heat_total_gwh']):.3f} GWh/day`",
                f"- Outdoor mean / min: `{float(item['t_outdoor_mean_c']):.2f} C` / `{float(item['t_outdoor_min_c']):.2f} C`",
                f"- MC auction mean / peak: `{float(item['mc_auction_mean_eur_mwh']):.2f}` / `{float(item['mc_auction_peak_eur_mwh']):.2f} EUR/MWh`",
                "",
            ]
        )
    (output_dir / "representative_days.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def _save_plot(
    *,
    output_dir: Path,
    daily: pd.DataFrame,
    selected: list[dict[str, object]],
) -> None:
    selected_dates = [pd.Timestamp(item["date"]) for item in selected]
    selected_labels = [str(item["label"]) for item in selected]

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))

    axes[0, 0].plot(daily.index, daily["dh_space_heat_total_kwh"] / 1e6, color="#b45309", linewidth=1.3)
    axes[0, 0].set_title("Daily DH space heat")
    axes[0, 0].set_ylabel("GWh/day")
    axes[0, 0].grid(True, alpha=0.25)

    axes[0, 1].plot(daily.index, daily["t_outdoor_mean_c"], color="#2563eb", linewidth=1.3)
    axes[0, 1].set_title("Daily outdoor mean temperature")
    axes[0, 1].set_ylabel("C")
    axes[0, 1].grid(True, alpha=0.25)

    axes[1, 0].plot(daily.index, daily["mc_auction_mean_eur_mwh"], color="#7c3aed", linewidth=1.3)
    axes[1, 0].set_title("Daily day-ahead price")
    axes[1, 0].set_ylabel("EUR/MWh")
    axes[1, 0].grid(True, alpha=0.25)

    scatter = axes[1, 1].scatter(
        daily["dh_space_heat_total_kwh"] / 1e6,
        daily["mc_auction_mean_eur_mwh"],
        c=daily["t_outdoor_mean_c"],
        cmap="coolwarm",
        alpha=0.7,
    )
    axes[1, 1].set_title("Heat vs day-ahead price")
    axes[1, 1].set_xlabel("DH space heat [GWh/day]")
    axes[1, 1].set_ylabel("MC auction [EUR/MWh]")
    axes[1, 1].grid(True, alpha=0.25)
    cbar = fig.colorbar(scatter, ax=axes[1, 1])
    cbar.set_label("Outdoor mean temperature [C]")

    for ax in axes.flat[:3]:
        for date in selected_dates:
            ax.axvline(date, color="#dc2626", linestyle="--", linewidth=0.9, alpha=0.6)
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))

    for item in selected:
        date = pd.Timestamp(item["date"])
        row = daily.loc[date]
        axes[1, 1].annotate(
            str(item["label"]).replace("_", "\n"),
            (float(row["dh_space_heat_total_kwh"]) / 1e6, float(row["mc_auction_mean_eur_mwh"])),
            textcoords="offset points",
            xytext=(6, 6),
            fontsize=8,
        )

    fig.tight_layout()
    fig.savefig(output_dir / "representative_days.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def _flatten_columns(columns: pd.Index) -> list[str]:
    flat: list[str] = []
    for col in columns:
        if not isinstance(col, tuple):
            flat.append(str(col))
            continue
        flat.append("_".join(str(part) for part in col if str(part)))
    return flat
