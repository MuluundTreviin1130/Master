from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd

from Learning.datasets.row_content_signature import normalized_rows_sha256
from Learning.datasets.save_dataset import save_dataset
from Learning.registry.register_dataset import register_dataset
from Learning.thermflex_daily_results.features import add_engineered_feature_columns
from Learning.thermflex_daily_results.schema import (
    BUILDER_METADATA_COLUMNS,
    CATEGORICAL_FEATURE_COLUMNS,
    CONTEXT_FEATURE_COLUMNS,
    DISPATCH_ECONOMICS_ENGINEERED_FEATURE_COLUMNS,
    DISPATCH_ECONOMICS_REFERENCE_FEATURE_COLUMNS,
    DISPATCH_STATE_ENGINEERED_FEATURE_COLUMNS,
    DISPATCH_STATE_REFERENCE_FEATURE_COLUMNS,
    ENGINEERED_FEATURE_COLUMNS,
    CORE_TARGET_COLUMNS,
    OPTIONAL_DISPATCH_ECONOMICS_TARGET_COLUMNS,
    POLICY_DESCRIPTOR_COLUMNS,
    REFERENCE_FEATURE_COLUMNS,
    REQUIRED_DAILY_RESULT_COLUMNS,
    TARGET_COLUMNS,
    validate_daily_results_frame,
)
from Optimization.run.analysis.dh_thermflex_inputs import load_vienna_dh_thermflex_full_year_context
from Optimization.run.analysis.select_vienna_dh_thermflex_representative_days import _build_daily_features
from Settings import get_settings

_BUNDLE_PREFIX = "daily_thermflex_screen_"
_RUN_SLUG_PATTERN = re.compile(r"^daily_thermflex_screen_(?P<run_slug>.+?)_\d{8}_\d{6}$")
_MD_OVERRIDE_PATTERN = re.compile(r"- `[^`]+`: `(?P<override>[^`]+\.json)`")
_LEGACY_FLEX_COLUMN_RENAMES: dict[str, str] = {
    "dispatch_operating_cost_eur_upper_1h": "dispatch_operating_cost_eur_flex",
    "co2_emissions_total_t_upper_1h": "co2_emissions_total_t_flex",
    "district_gas_boiler_peak_kw_upper_1h": "district_gas_boiler_peak_kw_flex",
    "district_gas_boiler_generation_kwh_upper_1h": "district_gas_boiler_generation_kwh_flex",
    "upper_case_label": "flex_case_label",
}
_LEGACY_REQUIRED_INPUT_COLUMNS: tuple[str, ...] = (
    "dispatch_operating_cost_eur_upper_1h",
    "co2_emissions_total_t_upper_1h",
    "district_gas_boiler_peak_kw_upper_1h",
    "district_gas_boiler_generation_kwh_upper_1h",
)
_OVERRIDE_DIR = (
    Path(__file__).resolve().parents[2]
    / "Optimization"
    / "validation"
    / "model_validation"
    / "overrides"
    / "thermflex"
)
_BASE_REF_OVERRIDE = (
    _OVERRIDE_DIR / "vienna_ref2023_dh_baseline_constant_no_thermflex_paper_day_ahead.json"
)
_DEFAULT_DATASET_ROOT = Path(__file__).resolve().parents[2] / "Learning" / "datasets"
_DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "Learning" / "registry" / "registry.json"


@dataclass(frozen=True)
class CuratedDatasetResult:
    family_hash: str
    dataset_id: str
    dataset_root: Path
    truth_rows: int
    selected_rows: int
    selected_bundle_count: int
    selected_bundles: tuple[str, ...]
    feature_columns: tuple[str, ...]
    target_columns: tuple[str, ...]


def discover_screen_csvs(
    *,
    source_root: Path,
    include_checkpoints: bool = False,
    min_checkpoint_rows: int = 30,
) -> list[Path]:
    """Return completed screens and optionally larger checkpoint tables under one root."""

    root = Path(source_root).resolve()
    if not root.exists():
        raise FileNotFoundError(f"[thermflex_daily_results] source root not found: {root}")
    matches = sorted(root.rglob("heating_season_day_screen.csv"))
    final_by_bundle: dict[Path, Path] = {path.parent.resolve(): path for path in matches}
    if include_checkpoints:
        for checkpoint_path in sorted(root.rglob("heating_season_day_screen_checkpoint.csv")):
            final_path = checkpoint_path.parent / "heating_season_day_screen.csv"
            row_count = _count_csv_rows(checkpoint_path)
            if row_count < int(min_checkpoint_rows):
                continue
            if final_path.exists():
                final_row_count = _count_csv_rows(final_path)
                # Partial screen runs checkpoint after every solved day, but only
                # refresh the final CSV when the whole invocation returns
                # cleanly. If the process is interrupted or times out, the
                # checkpoint can therefore be the newer and larger truth source.
                # We only prefer it when it is explicitly larger than the stale
                # final export; otherwise the finished final CSV stays canonical.
                if row_count > final_row_count:
                    bundle_dir = checkpoint_path.parent.resolve()
                    if bundle_dir in final_by_bundle:
                        matches.remove(final_by_bundle[bundle_dir])
                    matches.append(checkpoint_path)
                continue
            if row_count >= int(min_checkpoint_rows):
                matches.append(checkpoint_path)
    if not matches:
        if include_checkpoints:
            needle = "`heating_season_day_screen.csv` or sufficiently large checkpoint files"
        else:
            needle = "`heating_season_day_screen.csv`"
        raise FileNotFoundError(f"[thermflex_daily_results] no {needle} found under {root}")
    return matches


def collect_unique_screen_csvs(*, source_roots: Sequence[Path]) -> tuple[list[Path], list[dict[str, str]]]:
    """
    Collect unique screen CSVs across multiple roots.

    Duplicate bundle names are resolved by root order: the first root wins and
    later duplicates are only recorded in the manifest.
    """

    selected: dict[str, Path] = {}
    skipped_duplicates: list[dict[str, str]] = []
    for root_like in source_roots:
        root = Path(root_like).resolve()
        for csv_path in discover_screen_csvs(source_root=root):
            bundle_name = csv_path.parent.name
            if bundle_name in selected:
                skipped_duplicates.append(
                    {
                        "bundle_name": bundle_name,
                        "kept_screen_csv": str(selected[bundle_name]),
                        "skipped_screen_csv": str(csv_path),
                        "reason": "duplicate_bundle_name_later_source_root",
                    }
                )
                continue
            selected[bundle_name] = csv_path
    return list(selected.values()), skipped_duplicates


def collect_unique_screen_tables(
    *,
    source_roots: Sequence[Path],
    include_checkpoints: bool = False,
    min_checkpoint_rows: int = 30,
) -> tuple[list[Path], list[dict[str, str]]]:
    """Collect unique final or checkpoint screen tables across multiple roots."""

    selected: dict[str, Path] = {}
    skipped_duplicates: list[dict[str, str]] = []
    for root_like in source_roots:
        root = Path(root_like).resolve()
        for csv_path in discover_screen_csvs(
            source_root=root,
            include_checkpoints=include_checkpoints,
            min_checkpoint_rows=min_checkpoint_rows,
        ):
            bundle_name = csv_path.parent.name
            if bundle_name in selected:
                skipped_duplicates.append(
                    {
                        "bundle_name": bundle_name,
                        "kept_screen_csv": str(selected[bundle_name]),
                        "skipped_screen_csv": str(csv_path),
                        "reason": "duplicate_bundle_name_later_source_root",
                    }
                )
                continue
            selected[bundle_name] = csv_path
    return list(selected.values()), skipped_duplicates


def load_daily_results_truth_table(
    *,
    screen_csv_paths: Iterable[Path],
    source_root: Path | None = None,
) -> pd.DataFrame:
    """
    Load and merge ThermFlex daily screen CSVs into one auditable truth table.

    The loader explicitly supports the current screen schema and one legacy
    upper-only schema. Legacy support is normalized deliberately and tagged via
    `source_schema_version`; there is no silent best-effort fallback.
    """

    rows: list[pd.DataFrame] = []
    source_root_resolved = None if source_root is None else Path(source_root).resolve()
    for csv_path_like in screen_csv_paths:
        csv_path = Path(csv_path_like).resolve()
        if not csv_path.exists():
            raise FileNotFoundError(f"[thermflex_daily_results] screen csv not found: {csv_path}")
        bundle_dir = csv_path.parent
        bundle_name = bundle_dir.name
        if not bundle_name.startswith(_BUNDLE_PREFIX):
            raise ValueError(
                "[thermflex_daily_results] screen csv is not inside a `daily_thermflex_screen_*` "
                f"bundle: {csv_path}"
            )
        run_slug_match = _RUN_SLUG_PATTERN.match(bundle_name)
        run_slug = run_slug_match.group("run_slug") if run_slug_match is not None else ""

        raw_df = pd.read_csv(csv_path)
        normalized_df, schema_version = _normalize_screen_frame(raw_df=raw_df, bundle_dir=bundle_dir)
        validate_daily_results_frame(normalized_df, source_label=str(csv_path))

        normalized_df = normalized_df.copy()
        normalized_df["date"] = pd.to_datetime(normalized_df["date"], errors="raise")
        normalized_df = _enrich_with_canonical_daily_context(normalized_df)
        normalized_df["day_of_year"] = normalized_df["date"].dt.dayofyear.astype(int)
        normalized_df["month"] = normalized_df["date"].dt.month.astype(int)
        normalized_df["day_of_week"] = normalized_df["date"].dt.dayofweek.astype(int)
        normalized_df["source_bundle_name"] = bundle_name
        normalized_df["source_bundle_run_slug"] = run_slug
        normalized_df["source_screen_csv"] = str(csv_path)
        normalized_df["source_screen_kind"] = "checkpoint" if "checkpoint" in csv_path.name else "final"
        normalized_df["source_snapshot_root"] = (
            "" if source_root_resolved is None else str(source_root_resolved)
        )
        normalized_df["source_schema_version"] = schema_version

        override_name = str(normalized_df["flex_override_name"].iloc[0]).strip()
        policy_meta = _load_policy_metadata(override_name=override_name)
        for key, value in policy_meta.items():
            normalized_df[key] = value
        exported_label = str(normalized_df["flex_case_label"].iloc[0]).strip()
        canonical_label = str(policy_meta["policy_case_label_canonical"]).strip()
        normalized_df["policy_case_label_matches_export"] = bool(exported_label == canonical_label)
        rows.append(normalized_df)

    if not rows:
        raise ValueError("[thermflex_daily_results] no screen CSV rows loaded.")

    combined = pd.concat(rows, ignore_index=True)
    bundle_counts = combined.groupby("source_bundle_name").size().to_dict()
    combined["bundle_row_count"] = combined["source_bundle_name"].map(bundle_counts).astype(int)
    combined["bundle_is_full_heating_season"] = combined["bundle_row_count"] >= 200
    combined["bundle_is_pilot"] = combined["source_bundle_name"].astype(str).str.contains("pilot", case=False)
    combined["split_group_bundle"] = combined["source_bundle_name"].astype(str)
    combined["split_group_case"] = combined["policy_case_label_canonical"].astype(str)
    combined["split_group_month"] = combined["date"].dt.strftime("%Y-%m")
    combined = combined.sort_values(["source_bundle_name", "date"]).reset_index(drop=True)
    expected = set(REQUIRED_DAILY_RESULT_COLUMNS).union(BUILDER_METADATA_COLUMNS)
    missing = expected.difference(combined.columns)
    if missing:
        raise ValueError(
            "[thermflex_daily_results] merged truth table missing expected columns: "
            + ", ".join(sorted(missing))
        )
    return combined


def export_curated_daily_results_dataset(
    *,
    source_roots: Sequence[Path],
    dataset_root: Path = _DEFAULT_DATASET_ROOT,
    registry_path: Path = _DEFAULT_REGISTRY_PATH,
    feature_mode: str = "default",
    include_partial_bundles: bool = False,
    include_pilot_bundles: bool = False,
    include_checkpoint_bundles: bool = False,
    min_checkpoint_rows: int = 30,
    include_legacy_bundles: bool = True,
) -> CuratedDatasetResult:
    """Persist the first curated ThermFlex daily-results dataset into `Learning/datasets/`."""

    if not source_roots:
        raise ValueError("[thermflex_daily_results] export requires at least one source root.")
    selected_csvs, skipped_duplicates = collect_unique_screen_tables(
        source_roots=source_roots,
        include_checkpoints=include_checkpoint_bundles,
        min_checkpoint_rows=min_checkpoint_rows,
    )
    truth = load_daily_results_truth_table(screen_csv_paths=selected_csvs)
    selected = truth.copy()
    selection_reasons: list[str] = []
    if not include_partial_bundles:
        selected = selected[selected["bundle_is_full_heating_season"]].copy()
        selection_reasons.append("exclude_partial_bundles")
    else:
        selected = selected[
            selected["bundle_is_full_heating_season"]
            | (selected["bundle_row_count"] >= int(min_checkpoint_rows))
        ].copy()
        selection_reasons.append("exclude_tiny_partial_bundles")
    if not include_pilot_bundles:
        selected = selected[~selected["bundle_is_pilot"]].copy()
        selection_reasons.append("exclude_pilot_bundles")
    if not include_legacy_bundles:
        selected = selected[selected["source_schema_version"] == "screen_v2_current"].copy()
        selection_reasons.append("exclude_legacy_bundles")
    if selected.empty:
        raise ValueError("[thermflex_daily_results] curated selection is empty after bundle filters.")
    selected, policy_day_deduplication = _deduplicate_policy_day_rows(selected)
    if policy_day_deduplication["dropped_rows"] > 0:
        selection_reasons.append("deduplicate_policy_day_rows")
    feature_mode_normalized = _normalize_feature_mode(feature_mode)
    if feature_mode_normalized == "dispatch_economics":
        selected, dispatch_economics_filter = _filter_complete_dispatch_economics_rows(selected)
        selection_reasons.append("require_dispatch_economics_complete_rows")
        if selected.empty:
            raise ValueError(
                "[thermflex_daily_results] curated selection is empty after requiring complete "
                "dispatch-economics feature rows."
            )
        dispatch_state_filter = None
    elif feature_mode_normalized == "dispatch_economics_stateful":
        selected, dispatch_economics_filter = _filter_complete_dispatch_economics_rows(selected)
        selection_reasons.append("require_dispatch_economics_complete_rows")
        selected, dispatch_state_filter = _filter_complete_dispatch_state_rows(selected)
        selection_reasons.append("require_dispatch_state_complete_rows")
        if selected.empty:
            raise ValueError(
                "[thermflex_daily_results] curated selection is empty after requiring complete "
                "dispatch-economics and dispatch-state feature rows."
            )
    else:
        dispatch_economics_filter = None
        dispatch_state_filter = None
    selected = add_engineered_feature_columns(
        selected,
        include_dispatch_economics=feature_mode_normalized
        in {"dispatch_economics", "dispatch_economics_stateful"},
        include_dispatch_state=feature_mode_normalized == "dispatch_economics_stateful",
    )

    numeric_feature_columns = _resolved_numeric_feature_columns(feature_mode=feature_mode_normalized)
    _validate_feature_columns_complete(
        selected,
        feature_columns=numeric_feature_columns,
        feature_mode=feature_mode_normalized,
    )
    categorical_feature_columns = tuple(CATEGORICAL_FEATURE_COLUMNS)
    target_columns = tuple(TARGET_COLUMNS)
    missing_required_targets = sorted(set(CORE_TARGET_COLUMNS).difference(selected.columns))
    if missing_required_targets:
        raise KeyError(
            "[thermflex_daily_results] curated truth is missing required target columns: "
            + ", ".join(missing_required_targets)
        )
    missing_optional_targets = sorted(
        set(OPTIONAL_DISPATCH_ECONOMICS_TARGET_COLUMNS).difference(selected.columns)
    )
    for column in missing_optional_targets:
        selected[column] = np.nan

    x_design_df = selected.loc[:, list(numeric_feature_columns)].copy()
    x_design_df["date"] = pd.to_datetime(x_design_df["date"], errors="raise").map(pd.Timestamp.toordinal)
    x_design_df = x_design_df.apply(pd.to_numeric, errors="raise")

    x_encoded = pd.get_dummies(
        selected.loc[:, list(numeric_feature_columns) + list(categorical_feature_columns)].copy(),
        columns=list(categorical_feature_columns),
        dtype=float,
    )
    x_encoded["date"] = pd.to_datetime(selected["date"], errors="raise").map(pd.Timestamp.toordinal)
    x_encoded = x_encoded.apply(pd.to_numeric, errors="raise")

    y_df = selected.loc[:, list(target_columns)].apply(pd.to_numeric, errors="raise")
    selected_bundle_signatures = _selected_bundle_signatures(truth=truth, selected=selected)
    family_spec = {
        "family_name": "thermflex_daily_results",
        "schema_version": "thermflex_daily_results_v1",
        "source_roots": [str(Path(root).resolve()) for root in source_roots],
        "selected_bundle_names": sorted(selected["source_bundle_name"].astype(str).unique().tolist()),
        "selected_bundle_signatures": selected_bundle_signatures,
        "policy_day_deduplication": policy_day_deduplication,
        "dispatch_economics_filter": dispatch_economics_filter,
        "dispatch_state_filter": dispatch_state_filter,
        "missing_optional_target_columns": missing_optional_targets,
        "feature_mode": feature_mode_normalized,
        "feature_columns": list(numeric_feature_columns),
        "categorical_feature_columns": list(categorical_feature_columns),
        "target_columns": list(target_columns),
        "selection_reasons": selection_reasons,
        "include_partial_bundles": bool(include_partial_bundles),
        "include_pilot_bundles": bool(include_pilot_bundles),
        "include_checkpoint_bundles": bool(include_checkpoint_bundles),
        "min_checkpoint_rows": int(min_checkpoint_rows),
        "include_legacy_bundles": bool(include_legacy_bundles),
    }
    family_hash = _hash_family_spec(family_spec)
    dataset_id = f"thermflex_daily_results_{family_hash[:12]}"

    meta = {
        "dataset_kind": "thermflex_daily_results_curated",
        "family_hash": family_hash,
        "dataset_id": dataset_id,
        "n_truth_rows_total": int(len(truth)),
        "n_selected_rows": int(len(selected)),
        "n_selected_bundles": int(selected["source_bundle_name"].nunique()),
        "feature_mode": feature_mode_normalized,
        "feature_columns": list(numeric_feature_columns),
        "categorical_feature_columns": list(categorical_feature_columns),
        "encoded_feature_columns": [str(col) for col in x_encoded.columns],
        "target_columns": list(target_columns),
        "missing_optional_target_columns": missing_optional_targets,
        "group_columns": ["split_group_bundle", "split_group_case", "split_group_month"],
    }
    dataset_info = save_dataset(
        dataset_root,
        family_hash,
        x_design_df.to_numpy(dtype=float),
        x_encoded.to_numpy(dtype=float),
        y_df.to_numpy(dtype=float),
        meta,
        bounds_names=list(numeric_feature_columns),
        target_names=list(target_columns),
        family_spec=family_spec,
        source_runs=_source_runs_manifest(
            truth=truth,
            selected=selected,
            skipped_duplicates=skipped_duplicates,
        ),
    )

    truth_csv_path = Path(dataset_info["truth_csv_path"])
    truth_meta_path = Path(dataset_info["truth_meta_path"])
    selected.to_csv(truth_csv_path, index=False)
    truth_meta_path.write_text(
        json.dumps(
            {
                "dataset_kind": "thermflex_daily_results_curated_truth",
                "family_hash": family_hash,
                "dataset_id": dataset_id,
                "rows_total_before_selection": int(len(truth)),
                "rows_after_selection": int(len(selected)),
                "selected_bundle_names": sorted(selected["source_bundle_name"].astype(str).unique().tolist()),
                "excluded_bundle_names": sorted(
                    set(truth["source_bundle_name"].astype(str).unique().tolist())
                    - set(selected["source_bundle_name"].astype(str).unique().tolist())
                ),
                "selection_reasons": selection_reasons,
                "policy_day_deduplication": policy_day_deduplication,
                "dispatch_economics_filter": dispatch_economics_filter,
                "dispatch_state_filter": dispatch_state_filter,
                "missing_optional_target_columns": missing_optional_targets,
                "feature_mode": feature_mode_normalized,
                "raw_columns": list(selected.columns),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    settings_stub = SimpleNamespace(
        learning=SimpleNamespace(
            registry_path=str(registry_path),
        )
    )
    register_dataset(
        settings_stub,
        family_hash,
        dataset_id,
        {
            "source": "thermflex_daily_results_curated",
            "artifact_path": str(dataset_info["data_path"]),
            "meta_path": str(dataset_info["meta_path"]),
            "truth_csv_path": str(dataset_info["truth_csv_path"]),
            "truth_meta_path": str(dataset_info["truth_meta_path"]),
            "family_spec_path": str(dataset_info["family_spec_path"]) if dataset_info["family_spec_path"] else "",
            "source_runs_path": str(dataset_info["source_runs_path"]) if dataset_info["source_runs_path"] else "",
            "n_samples": int(len(selected)),
            "n_truth_rows_total": int(len(truth)),
            "is_active": True,
        },
    )
    return CuratedDatasetResult(
        family_hash=family_hash,
        dataset_id=dataset_id,
        dataset_root=Path(dataset_info["root"]),
        truth_rows=int(len(truth)),
        selected_rows=int(len(selected)),
        selected_bundle_count=int(selected["source_bundle_name"].nunique()),
        selected_bundles=tuple(sorted(selected["source_bundle_name"].astype(str).unique().tolist())),
        feature_columns=tuple(numeric_feature_columns),
        target_columns=target_columns,
    )


def _normalize_feature_mode(feature_mode: str) -> str:
    normalized = str(feature_mode).strip().lower()
    allowed = {"default", "dispatch_economics", "dispatch_economics_stateful"}
    if normalized not in allowed:
        raise ValueError(
            "[thermflex_daily_results] unsupported feature_mode "
            f"'{feature_mode}'. Expected one of: {', '.join(sorted(allowed))}."
        )
    return normalized


def _resolved_numeric_feature_columns(*, feature_mode: str = "default") -> tuple[str, ...]:
    feature_mode_normalized = _normalize_feature_mode(feature_mode)
    extra_engineered = (
        DISPATCH_ECONOMICS_ENGINEERED_FEATURE_COLUMNS
        if feature_mode_normalized in {"dispatch_economics", "dispatch_economics_stateful"}
        else ()
    )
    extra_reference = (
        DISPATCH_ECONOMICS_REFERENCE_FEATURE_COLUMNS
        if feature_mode_normalized in {"dispatch_economics", "dispatch_economics_stateful"}
        else ()
    )
    extra_state_engineered = (
        DISPATCH_STATE_ENGINEERED_FEATURE_COLUMNS
        if feature_mode_normalized == "dispatch_economics_stateful"
        else ()
    )
    extra_state_reference = (
        DISPATCH_STATE_REFERENCE_FEATURE_COLUMNS
        if feature_mode_normalized == "dispatch_economics_stateful"
        else ()
    )
    return tuple(
        column
        for column in (
            *POLICY_DESCRIPTOR_COLUMNS,
            *CONTEXT_FEATURE_COLUMNS,
            *ENGINEERED_FEATURE_COLUMNS,
            *extra_engineered,
            *extra_state_engineered,
            *REFERENCE_FEATURE_COLUMNS,
            *extra_reference,
            *extra_state_reference,
        )
        if column
        not in {
            "flex_case_label",
            "flex_override_name",
            "source_bundle_run_slug",
            "policy_case_label_canonical",
        }
    )


def _validate_feature_columns_complete(
    frame: pd.DataFrame,
    *,
    feature_columns: tuple[str, ...],
    feature_mode: str,
) -> None:
    missing = sorted(set(feature_columns).difference(frame.columns))
    if missing:
        raise KeyError(
            "[thermflex_daily_results] resolved feature columns missing from selected truth for "
            f"feature_mode={feature_mode}: "
            + ", ".join(missing)
        )
    incomplete = sorted(column for column in feature_columns if frame[column].isna().any())
    if incomplete:
        raise ValueError(
            "[thermflex_daily_results] resolved feature columns contain missing values for "
            f"feature_mode={feature_mode}: "
            + ", ".join(incomplete)
        )


def _filter_complete_dispatch_economics_rows(selected: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    required_columns = tuple(DISPATCH_ECONOMICS_REFERENCE_FEATURE_COLUMNS)
    missing = sorted(set(required_columns).difference(selected.columns))
    if missing:
        raise KeyError(
            "[thermflex_daily_results] dispatch_economics feature mode requires screen-export columns: "
            + ", ".join(missing)
        )
    complete_mask = ~selected.loc[:, list(required_columns)].isna().any(axis=1)
    filtered = selected.loc[complete_mask].copy()
    return filtered, {
        "required_columns": list(required_columns),
        "input_rows": int(len(selected)),
        "output_rows": int(len(filtered)),
        "dropped_rows": int(len(selected) - len(filtered)),
        "retained_bundles": sorted(filtered["source_bundle_name"].astype(str).unique().tolist()),
    }


def _filter_complete_dispatch_state_rows(selected: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    required_columns = tuple(DISPATCH_STATE_REFERENCE_FEATURE_COLUMNS)
    missing = sorted(set(required_columns).difference(selected.columns))
    if missing:
        raise KeyError(
            "[thermflex_daily_results] dispatch_economics_stateful feature mode requires screen-export columns: "
            + ", ".join(missing)
        )
    complete_mask = ~selected.loc[:, list(required_columns)].isna().any(axis=1)
    filtered = selected.loc[complete_mask].copy()
    return filtered, {
        "required_columns": list(required_columns),
        "input_rows": int(len(selected)),
        "output_rows": int(len(filtered)),
        "dropped_rows": int(len(selected) - len(filtered)),
        "retained_bundles": sorted(filtered["source_bundle_name"].astype(str).unique().tolist()),
    }


def _deduplicate_policy_day_rows(selected: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Keep one canonical truth row for each exact policy-day key.

    Historic daily-screen bundles include repeated UPPER and partial tau checks.
    If the same policy descriptors and date appear twice with different target
    values, a supervised model receives identical features with conflicting
    labels. That makes high R2 impossible and hides a data-contract problem.
    The ranking is explicit and auditable:
    - exported label must match the override-derived canonical label,
    - current schema beats legacy schema,
    - final CSV beats checkpoint CSV,
    - larger bundles beat tiny partial duplicates,
    - newer timestamped bundle names break remaining ties.
    """

    key_columns = [
        "date",
        "policy_case_label_canonical",
        "policy_duration_h",
        "policy_lower_relaxation_k",
        "policy_tau_h",
        "policy_dispatch_horizon_h",
        "policy_dispatch_rolling_commit_h",
        "policy_max_events_per_day",
        "policy_constant_lower_bound_c",
    ]
    missing = sorted(set(key_columns).difference(selected.columns))
    if missing:
        raise KeyError(
            "[thermflex_daily_results] policy-day deduplication missing key columns: "
            + ", ".join(missing)
        )
    working = selected.copy()
    working["_dedup_rank_label_match"] = working["policy_case_label_matches_export"].astype(bool).astype(int)
    working["_dedup_rank_schema"] = (working["source_schema_version"].astype(str) == "screen_v2_current").astype(int)
    working["_dedup_rank_screen_kind"] = (working["source_screen_kind"].astype(str) == "final").astype(int)
    working["_dedup_rank_bundle_rows"] = pd.to_numeric(working["bundle_row_count"], errors="raise")
    working["_dedup_rank_bundle_timestamp"] = working["source_bundle_name"].astype(str).map(_extract_bundle_timestamp_rank)

    duplicate_mask = working.duplicated(subset=key_columns, keep=False)
    duplicate_rows = working.loc[duplicate_mask].copy()
    duplicate_group_count = int(duplicate_rows.groupby(key_columns, dropna=False).ngroups) if not duplicate_rows.empty else 0
    duplicate_target_ranges = _policy_day_duplicate_target_ranges(
        duplicate_rows=duplicate_rows,
        key_columns=key_columns,
    )

    ranked = working.sort_values(
        [
            *key_columns,
            "_dedup_rank_label_match",
            "_dedup_rank_schema",
            "_dedup_rank_screen_kind",
            "_dedup_rank_bundle_rows",
            "_dedup_rank_bundle_timestamp",
            "source_bundle_name",
            "source_screen_csv",
        ],
        ascending=[True] * len(key_columns) + [False, False, False, False, False, False, False],
    )
    kept = ranked.drop_duplicates(subset=key_columns, keep="first").copy()
    helper_columns = [column for column in kept.columns if column.startswith("_dedup_rank_")]
    kept = kept.drop(columns=helper_columns).sort_values(["source_bundle_name", "date"]).reset_index(drop=True)
    return kept, {
        "key_columns": key_columns,
        "input_rows": int(len(selected)),
        "output_rows": int(len(kept)),
        "dropped_rows": int(len(selected) - len(kept)),
        "duplicate_group_count": duplicate_group_count,
        "target_range_summary": duplicate_target_ranges,
    }


def _extract_bundle_timestamp_rank(bundle_name: str) -> str:
    matches = re.findall(r"(\d{8}_\d{6})", str(bundle_name))
    if not matches:
        return ""
    return matches[-1]


def _policy_day_duplicate_target_ranges(
    *,
    duplicate_rows: pd.DataFrame,
    key_columns: list[str],
) -> dict[str, dict[str, float]]:
    if duplicate_rows.empty:
        return {}
    summary: dict[str, dict[str, float]] = {}
    for target in TARGET_COLUMNS:
        if target not in duplicate_rows.columns:
            continue
        ranges = (
            duplicate_rows.groupby(key_columns, dropna=False)[target]
            .agg(lambda values: float(pd.to_numeric(values, errors="raise").max() - pd.to_numeric(values, errors="raise").min()))
            .to_numpy(dtype=float)
        )
        summary[target] = {
            "max_range": float(np.max(ranges)),
            "mean_range": float(np.mean(ranges)),
        }
    return summary


def _source_runs_manifest(
    *,
    truth: pd.DataFrame,
    selected: pd.DataFrame,
    skipped_duplicates: list[dict[str, str]],
) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    selected_bundle_names = set(selected["source_bundle_name"].astype(str).unique().tolist())
    for bundle_name, bundle_df in truth.groupby("source_bundle_name", sort=True):
        bundle_dir = Path(str(bundle_df["source_screen_csv"].iloc[0])).resolve().parent
        failure_summary = _read_bundle_failure_summary(bundle_dir=bundle_dir)
        manifest.append(
            {
                "bundle_name": str(bundle_name),
                "screen_csv": str(bundle_df["source_screen_csv"].iloc[0]),
                "screen_kind": str(bundle_df["source_screen_kind"].iloc[0]),
                "schema_version": str(bundle_df["source_schema_version"].iloc[0]),
                "rows": int(len(bundle_df)),
                "selected_for_training": str(bundle_name) in selected_bundle_names,
                "is_pilot": bool(bundle_df["bundle_is_pilot"].iloc[0]),
                "is_full_heating_season": bool(bundle_df["bundle_is_full_heating_season"].iloc[0]),
                "policy_case_label_canonical": str(bundle_df["policy_case_label_canonical"].iloc[0]),
                "policy_case_label_matches_export": bool(bundle_df["policy_case_label_matches_export"].iloc[0]),
                "failure_csv": failure_summary["failure_csv"],
                "known_failure_rows": failure_summary["known_failure_rows"],
                "known_failure_dates": failure_summary["known_failure_dates"],
            }
        )
    manifest.extend(skipped_duplicates)
    return manifest


def _selected_bundle_signatures(
    *,
    truth: pd.DataFrame,
    selected: pd.DataFrame,
) -> list[dict[str, Any]]:
    """
    Build a compact selected-bundle revision signature for dataset hashing.

    The daily curated family is not defined only by bundle names. Partial truth
    bundles evolve over time as more days are solved or explicit heavy-day
    failures are added. If the family hash ignores that evolution, a later and
    materially richer checkpoint silently reuses the old hash and overwrites the
    old model id. The signature below therefore keeps exactly the bundle facts
    that change the effective training truth:
    - which concrete screen table was selected (`final` vs `checkpoint`)
    - how many rows of truth it currently contributes
    - which explicit heavy-day failures are known beside that truth
    - a content digest of the selected rows that actually become X/Y, so
      in-place value revisions with unchanged structure cannot collide
    """

    selected_bundle_names = set(selected["source_bundle_name"].astype(str).unique().tolist())
    signatures: list[dict[str, Any]] = []
    for bundle_name, bundle_df in truth.groupby("source_bundle_name", sort=True):
        bundle_name_str = str(bundle_name)
        if bundle_name_str not in selected_bundle_names:
            continue
        bundle_dir = Path(str(bundle_df["source_screen_csv"].iloc[0])).resolve().parent
        failure_summary = _read_bundle_failure_summary(bundle_dir=bundle_dir)
        # Hash the selected rows that enter training, not merely the raw screen.
        selected_bundle = selected.loc[
            selected["source_bundle_name"].astype(str) == bundle_name_str
        ].copy()
        signatures.append(
            {
                "bundle_name": bundle_name_str,
                "screen_csv": str(bundle_df["source_screen_csv"].iloc[0]),
                "screen_kind": str(bundle_df["source_screen_kind"].iloc[0]),
                "rows": int(len(bundle_df)),
                "schema_version": str(bundle_df["source_schema_version"].iloc[0]),
                "known_failure_rows": int(failure_summary["known_failure_rows"]),
                "known_failure_dates": list(failure_summary["known_failure_dates"]),
                "selected_rows": int(len(selected_bundle)),
                "normalized_rows_sha256": normalized_rows_sha256(selected_bundle),
            }
        )
    return signatures


def _read_bundle_failure_summary(*, bundle_dir: Path) -> dict[str, Any]:
    """
    Read an explicit failure manifest next to one screen bundle when present.

    Partial ThermFlex truth is only useful for later training and audit if the
    missing days remain visible. This helper keeps that information attached to
    the curated dataset manifest instead of scattering it across ad hoc notes.
    """

    failure_csv = bundle_dir / "heating_season_day_screen_failures.csv"
    if not failure_csv.exists():
        return {
            "failure_csv": "",
            "known_failure_rows": 0,
            "known_failure_dates": [],
        }
    failure_df = pd.read_csv(failure_csv)
    if failure_df.empty:
        return {
            "failure_csv": str(failure_csv),
            "known_failure_rows": 0,
            "known_failure_dates": [],
        }
    if "date" not in failure_df.columns:
        raise KeyError(
            "[thermflex_daily_results] failure manifest missing required `date` column: "
            f"{failure_csv}"
        )
    return {
        "failure_csv": str(failure_csv),
        "known_failure_rows": int(len(failure_df)),
        "known_failure_dates": sorted(failure_df["date"].astype(str).unique().tolist()),
    }


def _normalize_screen_frame(*, raw_df: pd.DataFrame, bundle_dir: Path) -> tuple[pd.DataFrame, str]:
    """
    Normalize one bundle to the current explicit daily-results truth contract.

    Supported cases:
    - `screen_v2_current`: already exports `*_flex`, irradiance proxies and
      explicit `flex_case_label` / `flex_override_name`
    - `screen_v1_upper_legacy`: older upper-only export with `*_upper_1h`
      columns and missing irradiance/override metadata
    """

    df = raw_df.copy()
    if "dispatch_operating_cost_eur_flex" in df.columns and "flex_override_name" in df.columns:
        return df, "screen_v2_current"

    legacy_missing = [column for column in _LEGACY_REQUIRED_INPUT_COLUMNS if column not in df.columns]
    if legacy_missing:
        raise ValueError(
            "[thermflex_daily_results] unsupported screen schema in "
            f"{bundle_dir}: missing legacy compatibility columns {', '.join(legacy_missing)}"
        )

    df = df.rename(columns=_LEGACY_FLEX_COLUMN_RENAMES)
    override_name = _read_override_name_from_bundle_markdown(bundle_dir=bundle_dir)
    df["flex_override_name"] = override_name
    if "flex_case_label" not in df.columns or df["flex_case_label"].isna().all():
        df["flex_case_label"] = "UPPER_1H"
    current_context = _canonical_daily_context()
    join_columns = ["date", "irradiance_proxy_sum", "solargains_proxy_sum"]
    df["date"] = pd.to_datetime(df["date"], errors="raise").dt.strftime("%Y-%m-%d")
    df = df.merge(current_context[join_columns], on="date", how="left", validate="one_to_one")
    if df["irradiance_proxy_sum"].isna().any() or df["solargains_proxy_sum"].isna().any():
        raise ValueError(
            "[thermflex_daily_results] legacy bundle could not be enriched with irradiance proxies: "
            f"{bundle_dir}"
        )
    ordered_columns = [column for column in REQUIRED_DAILY_RESULT_COLUMNS if column in df.columns]
    remaining_columns = [column for column in df.columns if column not in ordered_columns]
    return df[ordered_columns + remaining_columns], "screen_v1_upper_legacy"


def _read_override_name_from_bundle_markdown(*, bundle_dir: Path) -> str:
    """Read the flex override name from the bundle markdown summary."""

    markdown_path = bundle_dir / "heating_season_day_screen.md"
    if not markdown_path.exists():
        raise FileNotFoundError(
            "[thermflex_daily_results] legacy bundle is missing markdown metadata: "
            f"{markdown_path}"
        )
    matches = _MD_OVERRIDE_PATTERN.findall(markdown_path.read_text(encoding="utf-8"))
    if len(matches) < 2:
        raise ValueError(
            "[thermflex_daily_results] could not parse REF/flex overrides from bundle markdown: "
            f"{markdown_path}"
        )
    return str(matches[1]).strip()


@lru_cache(maxsize=1)
def _canonical_daily_context() -> pd.DataFrame:
    """Build the canonical daily context once for legacy-schema enrichment."""

    context = load_vienna_dh_thermflex_full_year_context(base_override_path=_BASE_REF_OVERRIDE)
    daily = _build_daily_features(context).reset_index()
    daily = _add_canonical_daily_cohort_context(daily=daily, context=context)
    daily = _add_canonical_daily_shape_context(daily=daily, context=context)
    daily["t_outdoor_range_c"] = (
        pd.to_numeric(daily["t_outdoor_max_c"], errors="raise")
        - pd.to_numeric(daily["t_outdoor_min_c"], errors="raise")
    )
    daily["t_outdoor_mean_prevday_c"] = pd.to_numeric(
        daily["t_outdoor_mean_c"], errors="raise"
    ).shift(1)
    daily["t_outdoor_mean_nextday_c"] = pd.to_numeric(
        daily["t_outdoor_mean_c"], errors="raise"
    ).shift(-1)
    if daily["t_outdoor_mean_prevday_c"].isna().any():
        daily["t_outdoor_mean_prevday_c"] = daily["t_outdoor_mean_prevday_c"].fillna(
            daily["t_outdoor_mean_c"]
        )
    if daily["t_outdoor_mean_nextday_c"].isna().any():
        daily["t_outdoor_mean_nextday_c"] = daily["t_outdoor_mean_nextday_c"].fillna(
            daily["t_outdoor_mean_c"]
        )
    daily = _add_canonical_daily_temperature_memory(daily=daily)
    daily["date"] = pd.to_datetime(daily["date"], errors="raise").dt.strftime("%Y-%m-%d")
    return daily


def _add_canonical_daily_temperature_memory(*, daily: pd.DataFrame) -> pd.DataFrame:
    """
    Add explicit multi-day outdoor-temperature state features.

    Rebound and peak response depend on whether the building stock enters the
    flex day after a cold or mild spell. These features use only canonical
    weather context available before the dispatch solve: current-day forecast
    plus prior-day rolling windows. The first calendar day has no previous
    history inside the 2023 input frame, so its prior-window boundary is
    explicitly anchored to the current day instead of silently leaving NaNs.
    """

    df = daily.copy()
    df["date"] = pd.to_datetime(df["date"], errors="raise")
    df = df.sort_values("date").reset_index(drop=True)
    t_mean = pd.to_numeric(df["t_outdoor_mean_c"], errors="raise")
    t_min = pd.to_numeric(df["t_outdoor_min_c"], errors="raise")
    hdd18 = pd.to_numeric(df["hdd18_kh"], errors="raise")
    shifted_t_mean = t_mean.shift(1)
    shifted_t_min = t_min.shift(1)
    shifted_hdd18 = hdd18.shift(1)

    df["t_outdoor_mean_prev3d_c"] = shifted_t_mean.rolling(3, min_periods=1).mean().fillna(t_mean)
    df["t_outdoor_mean_prev7d_c"] = shifted_t_mean.rolling(7, min_periods=1).mean().fillna(t_mean)
    df["t_outdoor_min_prev3d_c"] = shifted_t_min.rolling(3, min_periods=1).min().fillna(t_min)
    df["t_outdoor_min_prev7d_c"] = shifted_t_min.rolling(7, min_periods=1).min().fillna(t_min)
    df["hdd18_prev3d_kh"] = shifted_hdd18.rolling(3, min_periods=1).sum().fillna(hdd18)
    df["hdd18_prev7d_kh"] = shifted_hdd18.rolling(7, min_periods=1).sum().fillna(hdd18)
    df["t_outdoor_mean_rolling3d_c"] = t_mean.rolling(3, min_periods=1).mean()
    df["t_outdoor_mean_rolling7d_c"] = t_mean.rolling(7, min_periods=1).mean()
    df["t_outdoor_min_rolling3d_c"] = t_min.rolling(3, min_periods=1).min()
    df["t_outdoor_min_rolling7d_c"] = t_min.rolling(7, min_periods=1).min()
    df["hdd18_rolling3d_kh"] = hdd18.rolling(3, min_periods=1).sum()
    df["hdd18_rolling7d_kh"] = hdd18.rolling(7, min_periods=1).sum()
    df["t_outdoor_mean_delta_vs_prev3d_c"] = t_mean - df["t_outdoor_mean_prev3d_c"]
    df["t_outdoor_mean_delta_vs_prev7d_c"] = t_mean - df["t_outdoor_mean_prev7d_c"]
    return df


def _add_canonical_daily_shape_context(
    *,
    daily: pd.DataFrame,
    context: Any,
) -> pd.DataFrame:
    """
    Attach explicit hourly-shape descriptors from the canonical yearly context.

    Daily means hide exactly the signals that drive dispatch cost and peak
    behavior: price spikes, load peaks, intraday ramps, and whether demand sits
    in high-price hours. These columns are deterministic reductions of the same
    hourly SSOT already used by the optimization runs.
    """

    required = {
        "timestamp",
        "dh_total_kwh",
        "dh_space_heat_total_kwh",
        "mc_auction_eur_mwh",
        "t_outdoor_c",
    }
    hourly = context.hourly_system_df.copy()
    missing = sorted(required.difference(hourly.columns))
    if missing:
        raise KeyError(
            "[thermflex_daily_results] canonical hourly-shape context missing required columns: "
            + ", ".join(missing)
        )
    hourly["timestamp"] = pd.to_datetime(hourly["timestamp"], errors="raise")
    hourly = hourly.sort_values("timestamp").reset_index(drop=True)
    hourly["date"] = hourly["timestamp"].dt.normalize()
    hourly["hour"] = hourly["timestamp"].dt.hour.astype(int)

    records: list[dict[str, float | pd.Timestamp]] = []
    for date, group in hourly.groupby("date", sort=True):
        dh_total = pd.to_numeric(group["dh_total_kwh"], errors="raise").to_numpy(dtype=float)
        dh_space = pd.to_numeric(group["dh_space_heat_total_kwh"], errors="raise").to_numpy(dtype=float)
        price = pd.to_numeric(group["mc_auction_eur_mwh"], errors="raise").to_numpy(dtype=float)
        t_outdoor = pd.to_numeric(group["t_outdoor_c"], errors="raise").to_numpy(dtype=float)
        hours = pd.to_numeric(group["hour"], errors="raise").to_numpy(dtype=int)
        if len(group) != 24:
            raise ValueError(
                "[thermflex_daily_results] canonical hourly-shape context expects 24 hourly rows per day; "
                f"{pd.Timestamp(date).date()} has {len(group)}."
            )
        if np.any(dh_total < 0.0) or np.any(dh_space < 0.0):
            raise ValueError(
                "[thermflex_daily_results] canonical hourly-shape context requires nonnegative DH demand."
            )
        dh_total_sum = float(np.sum(dh_total))
        dh_space_sum = float(np.sum(dh_space))
        dh_total_peak = float(np.max(dh_total))
        dh_space_peak = float(np.max(dh_space))
        if dh_total_sum <= 0.0 or dh_total_peak <= 0.0:
            raise ValueError(
                "[thermflex_daily_results] canonical hourly-shape context requires positive daily DH total."
            )
        price_min_hour = int(hours[int(np.argmin(price))])
        price_peak_hour = int(hours[int(np.argmax(price))])
        dh_total_peak_hour = int(hours[int(np.argmax(dh_total))])
        dh_space_peak_hour = _hour_of_max_or_zero(values=dh_space, hours=hours)
        t_min_hour = int(hours[int(np.argmin(t_outdoor))])
        t_max_hour = int(hours[int(np.argmax(t_outdoor))])
        top_price_idx = np.argsort(price)[-3:]
        bottom_price_idx = np.argsort(price)[:3]
        q25 = float(np.quantile(price, 0.25))
        q75 = float(np.quantile(price, 0.75))
        records.append(
            {
                "date": pd.Timestamp(date),
                "mc_auction_min_eur_mwh": float(np.min(price)),
                "mc_auction_std_eur_mwh": float(np.std(price, ddof=0)),
                "mc_auction_range_eur_mwh": float(np.max(price) - np.min(price)),
                "mc_auction_min_hour": float(price_min_hour),
                "mc_auction_peak_hour": float(price_peak_hour),
                "mc_auction_peak_above_mean_eur_mwh": float(np.max(price) - np.mean(price)),
                "mc_auction_mean_above_min_eur_mwh": float(np.mean(price) - np.min(price)),
                "mc_auction_weighted_dh_total_mean_eur_mwh": float(np.sum(price * dh_total) / dh_total_sum),
                "mc_auction_weighted_space_heat_mean_eur_mwh": _weighted_mean_or_zero(
                    weights=dh_space,
                    values=price,
                    denominator=dh_space_sum,
                ),
                "dh_total_peak_kw": dh_total_peak,
                "dh_space_heat_peak_kw": dh_space_peak,
                "dh_total_peak_hour": float(dh_total_peak_hour),
                "dh_space_heat_peak_hour": float(dh_space_peak_hour),
                "dh_total_load_factor": float(dh_total_sum / (dh_total_peak * 24.0)),
                "dh_space_heat_load_factor": _space_heat_load_factor(
                    total=dh_space_sum,
                    peak=dh_space_peak,
                ),
                "dh_total_ramp_abs_max_kwh": float(np.max(np.abs(np.diff(dh_total)))),
                "dh_space_heat_ramp_abs_max_kwh": float(np.max(np.abs(np.diff(dh_space)))),
                "dh_total_peak_to_price_min_distance_h": _cyclic_hour_distance(
                    dh_total_peak_hour,
                    price_min_hour,
                ),
                "dh_total_peak_to_price_peak_distance_h": _cyclic_hour_distance(
                    dh_total_peak_hour,
                    price_peak_hour,
                ),
                "dh_space_heat_peak_to_price_min_distance_h": _cyclic_hour_distance(
                    dh_space_peak_hour,
                    price_min_hour,
                ),
                "dh_space_heat_peak_to_price_peak_distance_h": _cyclic_hour_distance(
                    dh_space_peak_hour,
                    price_peak_hour,
                ),
                "price_at_dh_total_peak_eur_mwh": float(price[int(np.argmax(dh_total))]),
                "price_at_dh_space_heat_peak_eur_mwh": _value_at_peak_or_zero(values=dh_space, lookup=price),
                "price_dh_total_corr": _safe_corr(price, dh_total),
                "price_dh_space_heat_corr": _safe_corr(price, dh_space),
                "t_outdoor_min_hour": float(t_min_hour),
                "t_outdoor_max_hour": float(t_max_hour),
                "t_outdoor_ramp_abs_max_c_per_h": float(np.max(np.abs(np.diff(t_outdoor)))),
                "t_outdoor_ramp_abs_mean_c_per_h": float(np.mean(np.abs(np.diff(t_outdoor)))),
                "t_outdoor_at_price_min_c": float(t_outdoor[int(np.argmin(price))]),
                "t_outdoor_at_price_peak_c": float(t_outdoor[int(np.argmax(price))]),
                "t_outdoor_at_dh_total_peak_c": float(t_outdoor[int(np.argmax(dh_total))]),
                "t_outdoor_at_dh_space_heat_peak_c": _value_at_peak_or_zero(
                    values=dh_space,
                    lookup=t_outdoor,
                ),
                "night_t_outdoor_mean_c": _window_mean(t_outdoor, hours, {0, 1, 2, 3, 4, 5}),
                "morning_t_outdoor_mean_c": _window_mean(t_outdoor, hours, {6, 7, 8, 9, 10, 11}),
                "midday_t_outdoor_mean_c": _window_mean(t_outdoor, hours, {12, 13, 14, 15, 16, 17}),
                "evening_t_outdoor_mean_c": _window_mean(t_outdoor, hours, {18, 19, 20, 21, 22, 23}),
                "night_hdd18_kh": _window_hdd18_sum(t_outdoor, hours, {0, 1, 2, 3, 4, 5}),
                "morning_hdd18_kh": _window_hdd18_sum(t_outdoor, hours, {6, 7, 8, 9, 10, 11}),
                "midday_hdd18_kh": _window_hdd18_sum(t_outdoor, hours, {12, 13, 14, 15, 16, 17}),
                "evening_hdd18_kh": _window_hdd18_sum(t_outdoor, hours, {18, 19, 20, 21, 22, 23}),
                "night_dh_total_share": _window_share(dh_total, hours, {0, 1, 2, 3, 4, 5}),
                "morning_dh_total_share": _window_share(dh_total, hours, {6, 7, 8, 9, 10, 11}),
                "midday_dh_total_share": _window_share(dh_total, hours, {12, 13, 14, 15, 16, 17}),
                "evening_dh_total_share": _window_share(dh_total, hours, {18, 19, 20, 21, 22, 23}),
                "night_dh_space_heat_share": _window_share_or_zero(dh_space, hours, {0, 1, 2, 3, 4, 5}),
                "morning_dh_space_heat_share": _window_share_or_zero(dh_space, hours, {6, 7, 8, 9, 10, 11}),
                "midday_dh_space_heat_share": _window_share_or_zero(dh_space, hours, {12, 13, 14, 15, 16, 17}),
                "evening_dh_space_heat_share": _window_share_or_zero(dh_space, hours, {18, 19, 20, 21, 22, 23}),
                "high_price_dh_total_share": float(np.sum(dh_total[price >= q75]) / dh_total_sum),
                "low_price_dh_total_share": float(np.sum(dh_total[price <= q25]) / dh_total_sum),
                "high_price_dh_space_heat_share": _masked_share_or_zero(
                    values=dh_space,
                    mask=price >= q75,
                ),
                "low_price_dh_space_heat_share": _masked_share_or_zero(
                    values=dh_space,
                    mask=price <= q25,
                ),
                "top3_price_dh_total_share": float(np.sum(dh_total[top_price_idx]) / dh_total_sum),
                "bottom3_price_dh_total_share": float(np.sum(dh_total[bottom_price_idx]) / dh_total_sum),
                "top3_price_dh_space_heat_share": _indexed_share_or_zero(
                    values=dh_space,
                    indices=top_price_idx,
                ),
                "bottom3_price_dh_space_heat_share": _indexed_share_or_zero(
                    values=dh_space,
                    indices=bottom_price_idx,
                ),
            }
        )

    shape = pd.DataFrame.from_records(records)
    if shape.empty:
        raise ValueError("[thermflex_daily_results] canonical hourly-shape context produced no rows.")
    base = daily.copy()
    base["date"] = pd.to_datetime(base["date"], errors="raise")
    merged = base.merge(shape, on="date", how="left", validate="one_to_one")
    shape_columns = [column for column in shape.columns if column != "date"]
    missing_shape = [column for column in shape_columns if merged[column].isna().any()]
    if missing_shape:
        raise ValueError(
            "[thermflex_daily_results] canonical hourly-shape context missing merged columns: "
            + ", ".join(sorted(missing_shape))
        )
    return merged


def _weighted_mean_or_zero(*, weights: np.ndarray, values: np.ndarray, denominator: float) -> float:
    """Return a physical weighted mean; zero denominator means no space-heat load."""

    if denominator < 0.0:
        raise ValueError("[thermflex_daily_results] weighted mean denominator cannot be negative.")
    if denominator == 0.0:
        return 0.0
    return float(np.sum(values * weights) / denominator)


def _space_heat_load_factor(*, total: float, peak: float) -> float:
    """Return the space-heat load factor with an explicit no-space-heat branch."""

    if total < 0.0 or peak < 0.0:
        raise ValueError("[thermflex_daily_results] space-heat load factor requires nonnegative inputs.")
    if total == 0.0:
        return 0.0
    if peak <= 0.0:
        raise ValueError("[thermflex_daily_results] positive space heat requires a positive peak.")
    return float(total / (peak * 24.0))


def _hour_of_max_or_zero(*, values: np.ndarray, hours: np.ndarray) -> int:
    """Return the peak hour, using hour zero only for explicit no-load days."""

    if len(values) != len(hours):
        raise ValueError("[thermflex_daily_results] peak-hour lookup requires aligned arrays.")
    if np.any(values < 0.0):
        raise ValueError("[thermflex_daily_results] peak-hour lookup requires nonnegative values.")
    if float(np.max(values)) <= 0.0:
        return 0
    return int(hours[int(np.argmax(values))])


def _value_at_peak_or_zero(*, values: np.ndarray, lookup: np.ndarray) -> float:
    """Return the lookup value at the positive-load peak; no-load days use zero."""

    if len(values) != len(lookup):
        raise ValueError("[thermflex_daily_results] peak lookup requires aligned arrays.")
    if np.any(values < 0.0):
        raise ValueError("[thermflex_daily_results] peak lookup requires nonnegative values.")
    if float(np.max(values)) <= 0.0:
        return 0.0
    return float(lookup[int(np.argmax(values))])


def _cyclic_hour_distance(left_hour: int, right_hour: int) -> float:
    """Return the shortest distance between two clock hours on a 24h circle."""

    left = int(left_hour) % 24
    right = int(right_hour) % 24
    raw = abs(left - right)
    return float(min(raw, 24 - raw))


def _safe_corr(left: np.ndarray, right: np.ndarray) -> float:
    """Return a correlation feature; constant vectors are explicitly uninformative."""

    if len(left) != len(right):
        raise ValueError("[thermflex_daily_results] correlation feature requires aligned arrays.")
    left_std = float(np.std(left, ddof=0))
    right_std = float(np.std(right, ddof=0))
    if left_std <= 1e-12 or right_std <= 1e-12:
        return 0.0
    return float(np.corrcoef(left, right)[0, 1])


def _window_share(values: np.ndarray, hours: np.ndarray, selected_hours: set[int]) -> float:
    total = float(np.sum(values))
    if total <= 0.0:
        raise ValueError("[thermflex_daily_results] hourly window shares require positive total demand.")
    mask = np.isin(hours, list(selected_hours))
    return float(np.sum(values[mask]) / total)


def _window_mean(values: np.ndarray, hours: np.ndarray, selected_hours: set[int]) -> float:
    """Return the mean value inside one fixed intraday window."""

    if len(values) != len(hours):
        raise ValueError("[thermflex_daily_results] window mean requires aligned arrays.")
    mask = np.isin(hours, list(selected_hours))
    if not bool(np.any(mask)):
        raise ValueError("[thermflex_daily_results] window mean selected no hourly rows.")
    return float(np.mean(values[mask]))


def _window_hdd18_sum(t_outdoor_c: np.ndarray, hours: np.ndarray, selected_hours: set[int]) -> float:
    """Return explicit heating-degree-hours for one fixed intraday window."""

    if len(t_outdoor_c) != len(hours):
        raise ValueError("[thermflex_daily_results] window HDD requires aligned arrays.")
    mask = np.isin(hours, list(selected_hours))
    if not bool(np.any(mask)):
        raise ValueError("[thermflex_daily_results] window HDD selected no hourly rows.")
    return float(np.sum(np.maximum(0.0, 18.0 - t_outdoor_c[mask])))


def _window_share_or_zero(values: np.ndarray, hours: np.ndarray, selected_hours: set[int]) -> float:
    """Return a window share with an explicit zero-load branch for space heat."""

    total = float(np.sum(values))
    if total < 0.0:
        raise ValueError("[thermflex_daily_results] hourly window shares require nonnegative demand.")
    if total == 0.0:
        return 0.0
    mask = np.isin(hours, list(selected_hours))
    return float(np.sum(values[mask]) / total)


def _masked_share_or_zero(*, values: np.ndarray, mask: np.ndarray) -> float:
    """Return demand share inside a boolean mask; zero total demand yields zero."""

    if len(values) != len(mask):
        raise ValueError("[thermflex_daily_results] masked share requires aligned arrays.")
    if np.any(values < 0.0):
        raise ValueError("[thermflex_daily_results] masked share requires nonnegative values.")
    total = float(np.sum(values))
    if total == 0.0:
        return 0.0
    return float(np.sum(values[mask]) / total)


def _indexed_share_or_zero(*, values: np.ndarray, indices: np.ndarray) -> float:
    """Return demand share at selected hour indices; zero total demand yields zero."""

    if np.any(values < 0.0):
        raise ValueError("[thermflex_daily_results] indexed share requires nonnegative values.")
    total = float(np.sum(values))
    if total == 0.0:
        return 0.0
    return float(np.sum(values[indices]) / total)


def _add_canonical_daily_cohort_context(
    *,
    daily: pd.DataFrame,
    context: Any,
) -> pd.DataFrame:
    """
    Attach cohort-resolved daily DH space-heat shares from the same yearly SSOT.

    The daily surrogate currently sees only system-level day aggregates. That is
    sufficient for cost-oriented signals, but weak for shift/rebound behavior
    that depends on which cohort dominates the thermal demand on a given day.
    We therefore add only one compact, fully deterministic cohort block:
    daily DH space-heat shares by building_key plus residential/non-residential
    totals. The inputs already exist in the canonical full-year ThermFlex
    context, so this stays additive and avoids any new side data source.
    """

    enriched = daily.copy()
    cohort_frames: list[pd.DataFrame] = []
    for building_key, frame in context.member_hourly_frames.items():
        if "timestamp" not in frame.columns or "dh_space_heat_kwh" not in frame.columns:
            raise KeyError(
                "[thermflex_daily_results] canonical cohort context requires `timestamp` and "
                f"`dh_space_heat_kwh` for building_key='{building_key}'."
            )
        cohort_daily = (
            frame.loc[:, ["timestamp", "dh_space_heat_kwh"]]
            .copy()
            .set_index("timestamp")
            .resample("D")
            .sum()
            .rename(columns={"dh_space_heat_kwh": f"dh_space_heat_kwh_{building_key}"})
            .reset_index()
            .rename(columns={"timestamp": "date"})
        )
        cohort_frames.append(cohort_daily)

    if not cohort_frames:
        raise ValueError("[thermflex_daily_results] canonical cohort context produced no building-key tables.")

    cohort_daily_df = cohort_frames[0]
    for next_frame in cohort_frames[1:]:
        cohort_daily_df = cohort_daily_df.merge(next_frame, on="date", how="inner", validate="one_to_one")
    if cohort_daily_df.empty:
        raise ValueError("[thermflex_daily_results] canonical cohort context merge produced no daily rows.")

    cohort_value_columns = [
        column for column in cohort_daily_df.columns if column.startswith("dh_space_heat_kwh_")
    ]
    if not cohort_value_columns:
        raise ValueError("[thermflex_daily_results] canonical cohort context has no cohort daily-value columns.")

    cohort_daily_df["date"] = pd.to_datetime(cohort_daily_df["date"], errors="raise")
    merged = enriched.merge(cohort_daily_df, on="date", how="left", validate="one_to_one")
    for column in cohort_value_columns:
        if merged[column].isna().any():
            raise ValueError(
                "[thermflex_daily_results] canonical cohort context missing merged cohort demand column "
                f"`{column}`."
            )

    total_space_heat = pd.to_numeric(merged["dh_space_heat_total_kwh"], errors="raise").to_numpy(dtype=float)
    negative_mask = total_space_heat < 0.0
    if np.any(negative_mask):
        raise ValueError(
            "[thermflex_daily_results] canonical cohort context requires nonnegative `dh_space_heat_total_kwh`."
        )
    zero_total_mask = total_space_heat == 0.0

    residential_share_columns: list[str] = []
    non_residential_share_columns: list[str] = []
    for value_column in cohort_value_columns:
        building_key = value_column.removeprefix("dh_space_heat_kwh_")
        share_column = f"dh_space_heat_share_{building_key}"
        cohort_values = pd.to_numeric(merged[value_column], errors="raise").to_numpy(dtype=float)
        if np.any(cohort_values < 0.0):
            raise ValueError(
                "[thermflex_daily_results] canonical cohort context requires nonnegative cohort daily space heat "
                f"for `{value_column}`."
            )
        if np.any(zero_total_mask & (np.abs(cohort_values) > 1e-9)):
            raise ValueError(
                "[thermflex_daily_results] canonical cohort context found nonzero cohort space heat on a day with "
                f"zero total DH space heat for `{value_column}`."
            )
        share_values = np.zeros_like(total_space_heat, dtype=float)
        positive_total_mask = total_space_heat > 0.0
        share_values[positive_total_mask] = cohort_values[positive_total_mask] / total_space_heat[positive_total_mask]
        merged[share_column] = share_values
        if building_key.startswith("residential_"):
            residential_share_columns.append(share_column)
        elif building_key.startswith("non_residential_"):
            non_residential_share_columns.append(share_column)
        else:
            raise ValueError(
                "[thermflex_daily_results] unexpected building_key in canonical cohort context: "
                f"'{building_key}'."
            )

    merged["dh_space_heat_share_residential_total"] = merged[residential_share_columns].sum(axis=1)
    merged["dh_space_heat_share_non_residential_total"] = merged[non_residential_share_columns].sum(axis=1)
    merged = merged.drop(columns=cohort_value_columns)
    return merged


def _enrich_with_canonical_daily_context(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add stable daily weather/state context from the canonical 2023 Vienna input.

    The screen CSV export intentionally stays compact. For learning we can still
    attach additional context that is already part of the same SSOT yearly input
    layer, as long as it is merged explicitly by date and fails loudly on gaps.
    This avoids inventing side data while giving the daily surrogate a richer
    view of outdoor conditions around each flex day.
    """

    context = _canonical_daily_context().copy()
    join_feature_cols = [
        column
        for column in CONTEXT_FEATURE_COLUMNS
        if column not in {"date", "day_of_year", "month", "day_of_week"} and column not in df.columns
    ]
    missing_context_cols = sorted(set(join_feature_cols).difference(context.columns))
    if missing_context_cols:
        raise KeyError(
            "[thermflex_daily_results] canonical context is missing configured context features: "
            + ", ".join(missing_context_cols)
        )
    join_cols = ["date", *join_feature_cols]
    enriched = df.copy()
    enriched["date"] = pd.to_datetime(enriched["date"], errors="raise").dt.strftime("%Y-%m-%d")
    enriched = enriched.merge(context[join_cols], on="date", how="left", validate="many_to_one")
    missing = [
        column
        for column in join_cols
        if column != "date" and enriched[column].isna().any()
    ]
    if missing:
        raise ValueError(
            "[thermflex_daily_results] canonical daily-context enrichment missing columns: "
            + ", ".join(sorted(missing))
        )
    enriched["date"] = pd.to_datetime(enriched["date"], errors="raise")
    return enriched


@lru_cache(maxsize=None)
def _load_policy_metadata(*, override_name: str) -> dict[str, Any]:
    """Resolve policy descriptors from the override file and active settings SSOT."""

    override_path = (_OVERRIDE_DIR / override_name).resolve()
    if not override_path.exists():
        raise FileNotFoundError(
            "[thermflex_daily_results] referenced ThermFlex override not found: "
            f"{override_path}"
        )
    overrides = json.loads(override_path.read_text(encoding="utf-8-sig"))
    settings = get_settings(overrides=overrides)
    thermflex_cfg = settings.constraints.thermflex
    dispatch_cfg = settings.dispatch
    heating_cfg = settings.heating_control
    setpoint_c = float(getattr(heating_cfg, "constant_setpoint_c", 0.0))
    lower_bound_c = float(getattr(thermflex_cfg, "constant_lower_bound_c", setpoint_c))
    lower_relaxation_k = float(setpoint_c - lower_bound_c)
    duration_h = float(getattr(thermflex_cfg, "max_flex_duration_h"))
    max_events_per_day = float(getattr(thermflex_cfg, "max_flex_events_per_day"))
    dispatch_contract = _dispatch_solve_contract(
        dispatch_cfg=dispatch_cfg,
        context_label=f"dispatch settings for {override_name}",
    )
    return {
        "policy_case_label_canonical": _build_canonical_case_label(
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
    }


def _dispatch_solve_contract(*, dispatch_cfg: Any, context_label: str) -> dict[str, float]:
    """Expose the MILP rolling-horizon contract as stable learning features."""

    horizon_h = _required_positive_int_attr(
        dispatch_cfg,
        "horizon_h",
        context_label=context_label,
    )
    rolling_commit_raw_h = _required_nonnegative_int_attr(
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


def _required_positive_int_attr(obj: Any, attr_name: str, *, context_label: str) -> int:
    value = _required_int_attr(obj, attr_name, context_label=context_label)
    if value <= 0:
        raise ValueError(
            "[thermflex_daily_results] required positive integer setting "
            f"`{attr_name}` must be > 0 in {context_label}, got {value}."
        )
    return value


def _required_nonnegative_int_attr(obj: Any, attr_name: str, *, context_label: str) -> int:
    value = _required_int_attr(obj, attr_name, context_label=context_label)
    if value < 0:
        raise ValueError(
            "[thermflex_daily_results] required nonnegative integer setting "
            f"`{attr_name}` must be >= 0 in {context_label}, got {value}."
        )
    return value


def _required_int_attr(obj: Any, attr_name: str, *, context_label: str) -> int:
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


def _build_canonical_case_label(
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


def _hash_family_spec(family_spec: dict[str, Any]) -> str:
    payload = json.dumps(family_spec, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _count_csv_rows(path: Path) -> int:
    """Count data rows in one CSV file without pulling it fully into pandas."""

    with path.open("r", encoding="utf-8") as handle:
        next(handle, None)
        return sum(1 for _ in handle)


def build_daily_results_dataset(*, source_root: Path, output_root: Path) -> None:
    """
    Legacy placeholder kept for call-site compatibility.

    The new canonical entry point is `export_curated_daily_results_dataset()`.
    """

    raise NotImplementedError(
        "[thermflex_daily_results] Use `export_curated_daily_results_dataset()` for the "
        "curated dataset export. The older placeholder entry point stays blocked on purpose."
    )
