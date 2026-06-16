from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

from Learning.datasets.save_dataset import save_dataset
from Learning.registry.register_dataset import register_dataset
from Optimization.run.analysis.dh_thermflex_inputs import load_vienna_dh_thermflex_full_year_context
from Optimization.run.analysis.select_vienna_dh_thermflex_representative_days import _build_daily_features
from Learning.thermflex_system_results.schema import (
    BUILDER_METADATA_COLUMNS,
    CATEGORICAL_FEATURE_COLUMNS,
    DERIVED_NUMERIC_FEATURE_COLUMNS,
    DISPATCH_KPI_TARGET_COLUMNS,
    DESIGN_FEATURE_COLUMNS,
    REQUIRED_COMMON_COLUMNS,
    TARGET_COLUMNS,
    validate_system_results_frame,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SOURCE_ROOT = _REPO_ROOT / "Optimization" / "run" / "results" / "Vienna" / "gold"
_DEFAULT_DATASET_ROOT = _REPO_ROOT / "Learning" / "datasets"
_DEFAULT_REGISTRY_PATH = _REPO_ROOT / "Learning" / "registry" / "registry.json"
_RUN_PREFIX_PATTERN = re.compile(r"^\d{8}_\d{6}_(?P<slug>.+)$")
_LOWER_BOUND_PATTERN = re.compile(r"lb(?P<int>\d+)p(?P<frac>\d+)")
_DURATION_PATTERN = re.compile(r"dur(?P<duration>\d+)")
_EVENT_PATTERN = re.compile(r"evt(?P<events>\d+)")
_DEFAULT_CONTEXT_OVERRIDE = (
    _REPO_ROOT
    / "Optimization"
    / "validation"
    / "model_validation"
    / "overrides"
    / "thermflex"
    / "vienna_ref2023_dh_baseline_constant_no_thermflex_paper_day_ahead.json"
)


@dataclass(frozen=True)
class CuratedDatasetResult:
    family_hash: str
    dataset_id: str
    dataset_root: Path
    truth_rows: int
    selected_rows: int
    selected_run_count: int
    selected_runs: tuple[str, ...]
    feature_columns: tuple[str, ...]
    target_columns: tuple[str, ...]


def discover_system_truth_csvs(
    *,
    source_root: Path = _DEFAULT_SOURCE_ROOT,
    include_smoke_runs: bool = False,
    require_dispatch_kpis: bool = False,
    required_dispatch_kpi_keys: tuple[str, ...] | None = None,
) -> list[Path]:
    """Discover historic ThermFlex system truth tables under the Vienna gold result root."""

    root = Path(source_root).resolve()
    if not root.exists():
        raise FileNotFoundError(f"[thermflex_system_results] source root not found: {root}")
    matches: list[Path] = []
    for csv_path in sorted(root.rglob("truth_dataset.csv")):
        parent_text = str(csv_path.parent).lower()
        if "thermflex" not in parent_text:
            continue
        if not include_smoke_runs and "gold_smoke" in parent_text:
            continue
        if require_dispatch_kpis and not (csv_path.parent / "dispatch_kpis.json").exists():
            continue
        if required_dispatch_kpi_keys is not None and not _dispatch_kpi_has_required_keys(
            csv_path.parent,
            required_keys=required_dispatch_kpi_keys,
        ):
            continue
        matches.append(csv_path)
    if not matches:
        raise FileNotFoundError("[thermflex_system_results] no compatible `truth_dataset.csv` files found.")
    return matches


def load_system_results_truth_table(
    *,
    truth_csv_paths: list[Path],
    dispatch_kpi_mode: str = "none",
) -> pd.DataFrame:
    """Load historic ThermFlex system truth tables into one explicit run-level truth frame."""

    dispatch_mode = str(dispatch_kpi_mode).strip().lower()
    if dispatch_mode not in {"none", "latest_point"}:
        raise ValueError(
            "[thermflex_system_results] dispatch_kpi_mode must be one of {'none', 'latest_point'}."
        )
    rows: list[pd.DataFrame] = []
    for csv_path in truth_csv_paths:
        csv_path = Path(csv_path).resolve()
        raw_df = pd.read_csv(csv_path)
        validate_system_results_frame(raw_df, source_label=str(csv_path))
        run_name = csv_path.parent.name
        run_slug = _strip_run_timestamp(run_name)
        dispatch_formulation_tag = _derive_dispatch_formulation_tag(run_slug)
        scenario_profile_tag = _derive_scenario_profile_tag(run_slug)
        scenario_slice_tag = _derive_scenario_slice_tag(run_slug)
        scenario_anchor_date = _derive_scenario_anchor_date(run_slug)
        thermflex_case_slug = _derive_thermflex_case_slug(run_slug)
        normalized_df = raw_df.loc[:, list(REQUIRED_COMMON_COLUMNS)].copy()
        normalized_df["source_run_name"] = run_name
        normalized_df["source_run_slug"] = run_slug
        normalized_df["source_truth_csv"] = str(csv_path)
        normalized_df["source_schema_version"] = f"thermflex_system_truth_n{len(raw_df.columns)}"
        normalized_df["dispatch_formulation_tag"] = dispatch_formulation_tag
        normalized_df["scenario_profile_tag"] = scenario_profile_tag
        normalized_df["scenario_slice_tag"] = scenario_slice_tag
        normalized_df["thermflex_case_slug"] = thermflex_case_slug
        normalized_df["policy_thermflex_enabled"] = float("no_thermflex" not in thermflex_case_slug)
        normalized_df["policy_no_thermflex"] = float("no_thermflex" in thermflex_case_slug)
        normalized_df["policy_lower_bound_c"] = _parse_lower_bound_c(thermflex_case_slug)
        normalized_df["policy_duration_h"] = _parse_duration_h(thermflex_case_slug)
        normalized_df["policy_max_events_per_day"] = _parse_max_events_per_day(thermflex_case_slug)
        normalized_df["scenario_is_baseline_constant"] = float(scenario_profile_tag == "baseline_constant")
        normalized_df["scenario_is_day_night"] = float(scenario_profile_tag == "day_night")
        normalized_df["scenario_is_peak_window"] = float(scenario_slice_tag == "peak")
        normalized_df["scenario_is_price_window"] = float(scenario_slice_tag == "price")
        normalized_df["scenario_is_sunny_window"] = float(scenario_slice_tag == "sunny")
        normalized_df["scenario_is_wintertyp_window"] = float(scenario_slice_tag == "wintertyp")
        normalized_df["scenario_is_shouldertyp_window"] = float(scenario_slice_tag == "shouldertyp")
        normalized_df["scenario_anchor_month"] = float("nan") if scenario_anchor_date is None else float(scenario_anchor_date.month)
        normalized_df["scenario_anchor_day_of_year"] = (
            float("nan") if scenario_anchor_date is None else float(int(scenario_anchor_date.strftime("%j")))
        )
        scenario_context = _lookup_scenario_daily_context(scenario_anchor_date)
        for key, value in scenario_context.items():
            normalized_df[key] = value
        if dispatch_mode == "latest_point":
            dispatch_rows = _load_dispatch_kpi_point_rows(csv_path.parent, expected_rows=len(raw_df))
            for key in DISPATCH_KPI_TARGET_COLUMNS:
                normalized_df[key] = [row[key] for row in dispatch_rows]
        normalized_df["split_group_run"] = run_name
        normalized_df["split_group_case"] = run_slug
        normalized_df["split_group_dispatch"] = dispatch_formulation_tag
        rows.append(normalized_df)
    if not rows:
        raise ValueError("[thermflex_system_results] no truth rows loaded.")
    combined = pd.concat(rows, ignore_index=True)
    expected = set(REQUIRED_COMMON_COLUMNS).union(BUILDER_METADATA_COLUMNS)
    missing = expected.difference(combined.columns)
    if missing:
        raise ValueError(
            "[thermflex_system_results] merged truth table missing expected columns: "
            + ", ".join(sorted(missing))
        )
    return combined.sort_values(["source_run_name", "signature_hash"]).reset_index(drop=True)


def export_curated_system_results_dataset(
    *,
    source_root: Path = _DEFAULT_SOURCE_ROOT,
    dataset_root: Path = _DEFAULT_DATASET_ROOT,
    registry_path: Path = _DEFAULT_REGISTRY_PATH,
    include_smoke_runs: bool = False,
    allowed_dispatch_tags: tuple[str, ...] | None = None,
    dispatch_kpi_mode: str = "none",
) -> CuratedDatasetResult:
    """Persist the first curated ThermFlex system-results dataset into `Learning/datasets/`."""

    dispatch_mode = str(dispatch_kpi_mode).strip().lower()
    truth_csvs = discover_system_truth_csvs(
        source_root=source_root,
        include_smoke_runs=include_smoke_runs,
        require_dispatch_kpis=(dispatch_mode == "latest_point"),
        required_dispatch_kpi_keys=(
            tuple(key for key in DISPATCH_KPI_TARGET_COLUMNS if key != "dispatch_heat_operating_cost_eur")
            if dispatch_mode == "latest_point"
            else None
        ),
    )
    truth = load_system_results_truth_table(truth_csv_paths=truth_csvs, dispatch_kpi_mode=dispatch_mode)
    if allowed_dispatch_tags is not None:
        allowed = {str(tag).strip() for tag in allowed_dispatch_tags if str(tag).strip()}
        if not allowed:
            raise ValueError("[thermflex_system_results] allowed_dispatch_tags was provided but empty.")
        truth = truth[truth["dispatch_formulation_tag"].astype(str).isin(sorted(allowed))].copy()
        if truth.empty:
            raise ValueError(
                "[thermflex_system_results] no truth rows left after dispatch-tag filter: "
                + ", ".join(sorted(allowed))
            )
    numeric_feature_columns = tuple(DESIGN_FEATURE_COLUMNS) + tuple(DERIVED_NUMERIC_FEATURE_COLUMNS)
    categorical_feature_columns = tuple(CATEGORICAL_FEATURE_COLUMNS)

    x_design_df = truth.loc[:, list(numeric_feature_columns)].apply(pd.to_numeric, errors="raise")
    x_encoded = pd.get_dummies(
        truth.loc[:, list(numeric_feature_columns) + list(categorical_feature_columns)].copy(),
        columns=list(categorical_feature_columns),
        dtype=float,
    ).apply(pd.to_numeric, errors="raise")
    target_columns = tuple(TARGET_COLUMNS)
    if dispatch_mode == "latest_point":
        target_columns = tuple(TARGET_COLUMNS) + tuple(DISPATCH_KPI_TARGET_COLUMNS)
    y_df = truth.loc[:, list(target_columns)].apply(pd.to_numeric, errors="raise")

    family_spec = {
        "family_name": "thermflex_system_results",
        "schema_version": "thermflex_system_results_v1",
        "source_root": str(Path(source_root).resolve()),
        "include_smoke_runs": bool(include_smoke_runs),
        "allowed_dispatch_tags": None if allowed_dispatch_tags is None else list(allowed_dispatch_tags),
        "dispatch_kpi_mode": dispatch_mode,
        "selected_run_names": sorted(truth["source_run_name"].astype(str).unique().tolist()),
        "feature_columns": list(numeric_feature_columns),
        "categorical_feature_columns": list(categorical_feature_columns),
        "target_columns": list(target_columns),
    }
    family_hash = _hash_family_spec(family_spec)
    dataset_id = f"thermflex_system_results_{family_hash[:12]}"

    meta = {
        "dataset_kind": "thermflex_system_results_curated",
        "family_hash": family_hash,
        "dataset_id": dataset_id,
        "n_truth_rows_total": int(len(truth)),
        "n_selected_rows": int(len(truth)),
        "n_selected_runs": int(truth["source_run_name"].nunique()),
        "feature_columns": list(numeric_feature_columns),
        "categorical_feature_columns": list(categorical_feature_columns),
        "encoded_feature_columns": [str(column) for column in x_encoded.columns],
        "target_columns": list(target_columns),
        "source_root": str(Path(source_root).resolve()),
        "include_smoke_runs": bool(include_smoke_runs),
        "allowed_dispatch_tags": None if allowed_dispatch_tags is None else list(allowed_dispatch_tags),
        "dispatch_kpi_mode": dispatch_mode,
    }
    saved = save_dataset(
        dataset_root,
        family_hash,
        X_design=x_design_df.to_numpy(dtype=float),
        X=x_encoded.to_numpy(dtype=float),
        Y=y_df.to_numpy(dtype=float),
        meta=meta,
        bounds_names=list(numeric_feature_columns),
        target_names=list(target_columns),
        family_spec=family_spec,
        source_runs=_build_source_runs_payload(truth),
    )
    truth_csv_path = Path(saved["truth_csv_path"])
    truth.to_csv(truth_csv_path, index=False)
    truth_meta_path = truth_csv_path.parent / "truth_dataset.meta.json"
    truth_meta_path.write_text(
        json.dumps(
            {
                "family_hash": family_hash,
                "dataset_id": dataset_id,
                "n_truth_rows": int(len(truth)),
                "n_source_runs": int(truth["source_run_name"].nunique()),
                "feature_columns": list(numeric_feature_columns),
                "categorical_feature_columns": list(categorical_feature_columns),
                "target_columns": list(target_columns),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    settings_stub = SimpleNamespace(learning=SimpleNamespace(registry_path=str(registry_path)))
    register_dataset(
        settings_stub,
        family_hash,
        dataset_id,
        {
            "source": "thermflex_system_results_export",
            "artifact_root": str(Path(saved["root"]).resolve()),
            "meta_path": str(Path(saved["meta_path"]).resolve()),
            "truth_csv_path": str(truth_csv_path.resolve()),
            "is_active": True,
            "signature_hash": family_hash,
        },
    )
    return CuratedDatasetResult(
        family_hash=family_hash,
        dataset_id=dataset_id,
        dataset_root=Path(saved["root"]).resolve(),
        truth_rows=int(len(truth)),
        selected_rows=int(len(truth)),
        selected_run_count=int(truth["source_run_name"].nunique()),
        selected_runs=tuple(sorted(truth["source_run_name"].astype(str).unique().tolist())),
        feature_columns=tuple(numeric_feature_columns),
        target_columns=tuple(target_columns),
    )


def _build_source_runs_payload(truth: pd.DataFrame) -> list[dict[str, Any]]:
    """Persist one auditable source entry per historic run folder."""

    rows: list[dict[str, Any]] = []
    for run_name, frame in truth.groupby("source_run_name", dropna=False):
        rows.append(
            {
                "source_run_name": str(run_name),
                "source_run_slug": str(frame["source_run_slug"].iloc[0]),
                "source_truth_csv": str(frame["source_truth_csv"].iloc[0]),
                "source_schema_version": str(frame["source_schema_version"].iloc[0]),
                "dispatch_formulation_tag": str(frame["dispatch_formulation_tag"].iloc[0]),
                "thermflex_case_slug": str(frame["thermflex_case_slug"].iloc[0]),
                "row_count": int(len(frame)),
            }
        )
    return sorted(rows, key=lambda item: item["source_run_name"])


def _strip_run_timestamp(run_name: str) -> str:
    """Remove the timestamp prefix from the historic result folder name."""

    match = _RUN_PREFIX_PATTERN.match(run_name)
    return match.group("slug") if match is not None else run_name


def _derive_dispatch_formulation_tag(run_slug: str) -> str:
    """Classify the broad run formulation from the run slug."""

    if "_paper_day_ahead" in run_slug:
        return "paper_day_ahead"
    if "_operations_two_stage" in run_slug:
        return "operations_two_stage"
    if "_gold_smoke" in run_slug:
        return "gold_smoke"
    return "other"


def _derive_scenario_profile_tag(run_slug: str) -> str:
    """Extract the main demand/setpoint profile tag from the run slug."""

    if "_baseline_constant_" in run_slug:
        return "baseline_constant"
    if "_day_night_" in run_slug:
        return "day_night"
    return "other"


def _derive_scenario_slice_tag(run_slug: str) -> str:
    """Extract the coarse scenario slice encoded in many paper run slugs."""

    for candidate in ("peak", "price", "sunny", "wintertyp", "shouldertyp"):
        if f"_{candidate}_" in run_slug:
            return candidate
    return "full_period"


def _derive_scenario_anchor_date(run_slug: str) -> datetime | None:
    """Extract a trailing YYYYMMDD anchor date when present in the run slug."""

    match = re.search(r"_(?P<datestr>\d{8})$", run_slug)
    if match is None:
        return None
    return datetime.strptime(match.group("datestr"), "%Y%m%d")


@lru_cache(maxsize=1)
def _system_daily_context_by_date() -> pd.DataFrame:
    """
    Load one explicit full-year daily context table for anchor-date enrichment.

    The system truth rows do not carry direct daily market/weather/load features.
    For anchored scenario slices, we therefore attach the canonical day-level
    context from the same Vienna paper-year SSOT that already underlies the
    daily ThermFlex analysis path.
    """

    context = load_vienna_dh_thermflex_full_year_context(base_override_path=_DEFAULT_CONTEXT_OVERRIDE)
    daily = _build_daily_features(context).reset_index()
    daily["date"] = pd.to_datetime(daily["date"], errors="raise").dt.normalize()
    daily = daily.loc[
        :,
        [
            "date",
            "t_outdoor_mean_c",
            "t_outdoor_min_c",
            "dh_total_kwh",
            "dh_space_heat_total_kwh",
            "solargains_proxy_sum",
            "irradiance_proxy_sum",
            "mc_auction_mean_eur_mwh",
            "mc_auction_peak_eur_mwh",
            "gas_price_mean_eur_mwh_fuel",
            "co2_price_mean_eur_tco2",
        ],
    ].copy()
    return daily.set_index("date", drop=True)


def _lookup_scenario_daily_context(anchor_date: datetime | None) -> dict[str, float]:
    """
    Resolve explicit daily context features for one anchored scenario row.

    Runs without an anchor date keep these fields as `NaN` on purpose. That
    makes the absence of day-specific context explicit instead of inventing a
    pseudo-day average for full-period cases.
    """

    feature_names = (
        "scenario_t_outdoor_mean_c",
        "scenario_t_outdoor_min_c",
        "scenario_dh_total_kwh",
        "scenario_dh_space_heat_total_kwh",
        "scenario_solargains_proxy_sum",
        "scenario_irradiance_proxy_sum",
        "scenario_mc_auction_mean_eur_mwh",
        "scenario_mc_auction_peak_eur_mwh",
        "scenario_gas_price_mean_eur_mwh_fuel",
        "scenario_co2_price_mean_eur_tco2",
    )
    if anchor_date is None:
        return {name: float("nan") for name in feature_names}

    lookup_date = pd.Timestamp(anchor_date).normalize()
    daily = _system_daily_context_by_date()
    if lookup_date not in daily.index:
        raise KeyError(
            "[thermflex_system_results] scenario anchor date not found in canonical daily context: "
            f"{lookup_date.date()}"
        )
    row = daily.loc[lookup_date]
    return {
        "scenario_t_outdoor_mean_c": float(row["t_outdoor_mean_c"]),
        "scenario_t_outdoor_min_c": float(row["t_outdoor_min_c"]),
        "scenario_dh_total_kwh": float(row["dh_total_kwh"]),
        "scenario_dh_space_heat_total_kwh": float(row["dh_space_heat_total_kwh"]),
        "scenario_solargains_proxy_sum": float(row["solargains_proxy_sum"]),
        "scenario_irradiance_proxy_sum": float(row["irradiance_proxy_sum"]),
        "scenario_mc_auction_mean_eur_mwh": float(row["mc_auction_mean_eur_mwh"]),
        "scenario_mc_auction_peak_eur_mwh": float(row["mc_auction_peak_eur_mwh"]),
        "scenario_gas_price_mean_eur_mwh_fuel": float(row["gas_price_mean_eur_mwh_fuel"]),
        "scenario_co2_price_mean_eur_tco2": float(row["co2_price_mean_eur_tco2"]),
    }


def _load_dispatch_kpi_point_rows(run_dir: Path, *, expected_rows: int) -> list[dict[str, float]]:
    """
    Load dispatch-KPI payloads in the same point order as `truth_dataset.csv`.

    The Gold engine appends one truth row and one dispatch-KPI `points` entry
    per evaluated design point. The learning target merge must therefore be
    row-wise; using `latest_point` for a multi-row run would broadcast the final
    design point's KPIs onto all earlier rows and corrupt labels silently.
    """

    if expected_rows <= 0:
        raise ValueError("[thermflex_system_results] expected dispatch KPI row count must be positive.")
    dispatch_path = Path(run_dir).resolve() / "dispatch_kpis.json"
    if not dispatch_path.exists():
        raise FileNotFoundError(
            "[thermflex_system_results] dispatch_kpi_mode='latest_point' requires dispatch_kpis.json: "
            f"{dispatch_path}"
        )
    payload = json.loads(dispatch_path.read_text(encoding="utf-8"))
    points = payload.get("points")
    if not isinstance(points, list):
        raise TypeError(
            "[thermflex_system_results] dispatch_kpis.json missing list field 'points': "
            f"{dispatch_path}"
        )
    if len(points) != expected_rows:
        raise ValueError(
            "[thermflex_system_results] dispatch KPI point count does not match truth rows: "
            f"{len(points)} points for {expected_rows} truth rows ({dispatch_path})"
        )

    merged_rows: list[dict[str, float]] = []
    for expected_idx, point in enumerate(points):
        if not isinstance(point, dict):
            raise TypeError(
                "[thermflex_system_results] dispatch_kpis.json point entry is not a dict: "
                f"points[{expected_idx}] ({dispatch_path})"
            )
        point_idx_raw = point.get("point_idx")
        if point_idx_raw is None:
            raise KeyError(
                "[thermflex_system_results] dispatch KPI point missing point_idx: "
                f"points[{expected_idx}] ({dispatch_path})"
            )
        if isinstance(point_idx_raw, bool):
            raise TypeError(
                "[thermflex_system_results] dispatch KPI point_idx must be an integer, not bool: "
                f"points[{expected_idx}] ({dispatch_path})"
            )
        if isinstance(point_idx_raw, float) and not point_idx_raw.is_integer():
            raise ValueError(
                "[thermflex_system_results] dispatch KPI point_idx must be an integer: "
                f"points[{expected_idx}]={point_idx_raw!r} ({dispatch_path})"
            )
        try:
            point_idx = int(point_idx_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "[thermflex_system_results] dispatch KPI point_idx must be parseable as integer: "
                f"points[{expected_idx}]={point_idx_raw!r} ({dispatch_path})"
            ) from exc
        if point_idx != expected_idx:
            raise ValueError(
                "[thermflex_system_results] dispatch KPI point_idx sequence does not match truth row order: "
                f"points[{expected_idx}].point_idx={point_idx} ({dispatch_path})"
            )
        merged_rows.append(
            _normalize_dispatch_kpi_point(
                point,
                dispatch_path=dispatch_path,
                point_label=f"points[{expected_idx}]",
            )
        )
    return merged_rows


def _normalize_dispatch_kpi_point(
    point: dict[str, Any],
    *,
    dispatch_path: Path,
    point_label: str,
) -> dict[str, float]:
    """Validate and coerce one dispatch-KPI JSON point to the target contract."""

    point_payload = dict(point)
    if "dispatch_heat_operating_cost_eur" not in point_payload:
        required_heat_terms = ("fuel_cost_eur", "co2_cost_eur", "variable_opex_eur")
        missing_heat_terms = [key for key in required_heat_terms if key not in point_payload]
        if missing_heat_terms:
            raise KeyError(
                "[thermflex_system_results] cannot derive dispatch_heat_operating_cost_eur because "
                f"required component KPIs are missing: {', '.join(missing_heat_terms)} "
                f"({point_label}, {dispatch_path})"
            )
        point_payload["dispatch_heat_operating_cost_eur"] = (
            float(point_payload["fuel_cost_eur"])
            + float(point_payload["co2_cost_eur"])
            + float(point_payload["variable_opex_eur"])
        )

    merged: dict[str, float] = {}
    for key in DISPATCH_KPI_TARGET_COLUMNS:
        if key not in point_payload:
            raise KeyError(
                "[thermflex_system_results] required dispatch KPI missing in dispatch point: "
                f"{key} ({point_label}, {dispatch_path})"
            )
        value = point_payload[key]
        if value is None:
            raise ValueError(
                "[thermflex_system_results] dispatch KPI must not be null in dispatch point: "
                f"{key} ({point_label}, {dispatch_path})"
            )
        merged[key] = float(value)
    return merged


def _dispatch_kpi_has_required_keys(run_dir: Path, *, required_keys: tuple[str, ...]) -> bool:
    """
    Check whether one run folder carries a compatible dispatch-KPI export.

    This is used only as an explicit family-selection rule for the richer
    dispatch-KPI learning contract. Older KPI exports remain valid historical
    artifacts, but they are excluded from this family instead of being silently
    coerced into the richer schema.
    """

    dispatch_path = Path(run_dir).resolve() / "dispatch_kpis.json"
    if not dispatch_path.exists():
        return False
    payload = json.loads(dispatch_path.read_text(encoding="utf-8"))
    points = payload.get("points")
    if not isinstance(points, list) or not points:
        return False
    for idx, point in enumerate(points):
        if not isinstance(point, dict):
            return False
        if not all(key in point for key in required_keys):
            return False
        try:
            _normalize_dispatch_kpi_point(
                point,
                dispatch_path=dispatch_path,
                point_label=f"points[{idx}]",
            )
        except (KeyError, TypeError, ValueError):
            return False
    return True


def _derive_thermflex_case_slug(run_slug: str) -> str:
    """Extract the ThermFlex-relevant case token from the run slug."""

    prefix_match = re.search(r"vienna_ref2023_dh_(baseline_constant|day_night)_(?P<case>.+)$", run_slug)
    if prefix_match is None:
        return "other"
    case_slug = prefix_match.group("case")
    for suffix in ("_paper_day_ahead", "_operations_two_stage", "_gold_smoke"):
        if case_slug.endswith(suffix):
            return case_slug[: -len(suffix)]
    return case_slug


def _parse_lower_bound_c(case_slug: str) -> float:
    """Parse lower-bound setpoint information from slugs such as `lb21p0`."""

    match = _LOWER_BOUND_PATTERN.search(case_slug)
    if match is None:
        return float("nan")
    return float(f"{match.group('int')}.{match.group('frac')}")


def _parse_duration_h(case_slug: str) -> float:
    """Parse ThermFlex maximum duration from slugs such as `dur8`."""

    match = _DURATION_PATTERN.search(case_slug)
    return float(match.group("duration")) if match is not None else float("nan")


def _parse_max_events_per_day(case_slug: str) -> float:
    """Parse event-count tags such as `evt1` from the case slug."""

    match = _EVENT_PATTERN.search(case_slug)
    return float(match.group("events")) if match is not None else float("nan")


def _hash_family_spec(family_spec: dict[str, Any]) -> str:
    """Create a deterministic family hash from the explicit family spec."""

    payload = json.dumps(family_spec, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
