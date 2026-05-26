from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence

import numpy as np
import pandas as pd

from Learning.datasets.save_dataset import save_dataset
from Learning.registry.register_dataset import register_dataset
from Learning.thermflex_daily_results.dataset_builder import _load_policy_metadata
from Learning.thermflex_hourly_dispatch.schema import (
    TARGET_COLUMNS,
    feature_columns,
    validate_hourly_dispatch_frame,
)
from Optimization.run.analysis.dh_thermflex_inputs import load_vienna_dh_thermflex_full_year_context

_DEFAULT_DATASET_ROOT = Path(__file__).resolve().parents[2] / "Learning" / "datasets"
_DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "Learning" / "registry" / "registry.json"
_DEFAULT_SOURCE_ROOT = Path(__file__).resolve().parents[2] / "Optimization" / "run" / "results" / "Vienna" / "gold"
_FINAL_FILENAME = "heating_season_hourly_dispatch.csv"
_CHECKPOINT_FILENAME = "heating_season_hourly_dispatch_checkpoint.csv"


@dataclass(frozen=True)
class CuratedDatasetResult:
    family_hash: str
    dataset_id: str
    dataset_root: Path
    truth_rows: int
    selected_rows: int
    selected_bundle_count: int
    feature_columns: tuple[str, ...]
    target_columns: tuple[str, ...]


def discover_hourly_dispatch_csvs(
    *,
    source_roots: Sequence[Path] = (_DEFAULT_SOURCE_ROOT,),
    include_checkpoints: bool = True,
    min_checkpoint_rows: int = 24,
) -> tuple[list[Path], list[dict[str, str]]]:
    """
    Locate reusable hourly dispatch truth tables in run-result folders.

    Completed bundle exports are preferred. A checkpoint is accepted only when
    explicitly enabled and either no final export exists or the checkpoint has
    more rows than a stale final export from an interrupted process.
    """

    selected: dict[str, Path] = {}
    skipped: list[dict[str, str]] = []
    for root_like in source_roots:
        root = Path(root_like).resolve()
        if not root.exists():
            raise FileNotFoundError(f"[thermflex_hourly_dispatch] source root not found: {root}")
        for csv_path in _discover_under_root(
            root=root,
            include_checkpoints=include_checkpoints,
            min_checkpoint_rows=min_checkpoint_rows,
        ):
            bundle_name = csv_path.parent.name
            if bundle_name in selected:
                skipped.append(
                    {
                        "bundle_name": bundle_name,
                        "kept_hourly_csv": str(selected[bundle_name]),
                        "skipped_hourly_csv": str(csv_path),
                        "reason": "duplicate_bundle_name_later_source_root",
                    }
                )
                continue
            selected[bundle_name] = csv_path
    if not selected:
        raise FileNotFoundError(
            "[thermflex_hourly_dispatch] no hourly dispatch truth CSV found under "
            + ", ".join(str(Path(root).resolve()) for root in source_roots)
        )
    return list(selected.values()), skipped


def load_hourly_dispatch_truth_table(*, hourly_csv_paths: Sequence[Path]) -> pd.DataFrame:
    """Load hourly REF/FLEX dispatch truth and attach stable policy descriptors."""

    rows: list[pd.DataFrame] = []
    for csv_path_like in hourly_csv_paths:
        csv_path = Path(csv_path_like).resolve()
        if not csv_path.exists():
            raise FileNotFoundError(f"[thermflex_hourly_dispatch] hourly dispatch csv not found: {csv_path}")
        raw = pd.read_csv(csv_path)
        validate_hourly_dispatch_frame(raw, source_label=str(csv_path))
        df = raw.copy()
        df["date"] = pd.to_datetime(df["date"], errors="raise")
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="raise")
        df["hour_index"] = pd.to_numeric(df["hour_index"], errors="raise").astype(int)
        df["source_bundle_name"] = csv_path.parent.name
        df["source_hourly_csv"] = str(csv_path)
        df["source_hourly_kind"] = "checkpoint" if csv_path.name == _CHECKPOINT_FILENAME else "final"
        df["source_bundle_run_slug"] = _run_slug_from_bundle_name(csv_path.parent.name)

        override_names = sorted(df["flex_override_name"].astype(str).str.strip().unique().tolist())
        if len(override_names) != 1:
            raise ValueError(
                "[thermflex_hourly_dispatch] hourly dispatch bundle must reference exactly one "
                f"ThermFlex override, got {override_names} in {csv_path}"
            )
        policy_meta = _load_policy_metadata(override_name=override_names[0])
        for key, value in policy_meta.items():
            df[key] = value
        exported_label = str(df["flex_case_label"].iloc[0]).strip()
        canonical_label = str(policy_meta["policy_case_label_canonical"]).strip()
        df["policy_case_label_matches_export"] = bool(exported_label == canonical_label)
        rows.append(df)
    if not rows:
        raise ValueError("[thermflex_hourly_dispatch] no hourly dispatch rows loaded.")

    combined = pd.concat(rows, ignore_index=True)
    combined = _enrich_with_system_hourly_context(combined)
    combined = _add_engineered_time_features(combined)
    combined["split_group_date"] = combined["date"].dt.strftime("%Y-%m-%d")
    combined["split_group_bundle"] = combined["source_bundle_name"].astype(str)
    combined["split_group_case"] = combined["flex_case_label"].astype(str)
    combined["split_group_policy_date"] = (
        combined["flex_override_name"].astype(str) + "::" + combined["split_group_date"].astype(str)
    )
    combined = combined.sort_values(
        ["source_bundle_name", "policy_case_label_canonical", "date", "hour_index"]
    ).reset_index(drop=True)
    _validate_unique_hourly_keys(combined)
    _validate_complete_numeric_columns(combined, columns=feature_columns() + TARGET_COLUMNS)
    return combined


def export_curated_hourly_dispatch_dataset(
    *,
    source_roots: Sequence[Path] = (_DEFAULT_SOURCE_ROOT,),
    dataset_root: Path = _DEFAULT_DATASET_ROOT,
    registry_path: Path = _DEFAULT_REGISTRY_PATH,
    include_checkpoints: bool = True,
    min_checkpoint_rows: int = 24,
) -> CuratedDatasetResult:
    """Persist curated hourly dispatch-flow truth into `Learning/datasets/`."""

    csv_paths, skipped_duplicates = discover_hourly_dispatch_csvs(
        source_roots=source_roots,
        include_checkpoints=include_checkpoints,
        min_checkpoint_rows=min_checkpoint_rows,
    )
    truth = load_hourly_dispatch_truth_table(hourly_csv_paths=csv_paths)
    selected, policy_hour_deduplication = _deduplicate_policy_hour_rows(truth)
    numeric_feature_columns = feature_columns()
    target_columns = TARGET_COLUMNS
    x_design = selected.loc[:, list(numeric_feature_columns)].apply(pd.to_numeric, errors="raise")
    x_encoded = x_design.copy()
    y_df = selected.loc[:, list(target_columns)].apply(pd.to_numeric, errors="raise")

    family_spec = {
        "dataset_kind": "thermflex_hourly_dispatch_curated",
        "schema_version": "thermflex_hourly_dispatch_v1",
        "source_roots": [str(Path(root).resolve()) for root in source_roots],
        "include_checkpoints": bool(include_checkpoints),
        "min_checkpoint_rows": int(min_checkpoint_rows),
        "feature_columns": list(numeric_feature_columns),
        "target_columns": list(target_columns),
        "selected_bundle_signatures": _selected_bundle_signatures(selected),
        "policy_hour_deduplication": policy_hour_deduplication,
    }
    family_hash = _hash_family_spec(family_spec)
    dataset_id = f"thermflex_hourly_dispatch_{family_hash[:12]}"
    meta = {
        "dataset_kind": "thermflex_hourly_dispatch_curated",
        "family_hash": family_hash,
        "dataset_id": dataset_id,
        "n_truth_rows_total": int(len(truth)),
        "n_selected_rows": int(len(selected)),
        "n_selected_bundles": int(selected["source_bundle_name"].nunique()),
        "feature_columns": list(numeric_feature_columns),
        "encoded_feature_columns": list(x_encoded.columns),
        "target_columns": list(target_columns),
        "policy_hour_deduplication": policy_hour_deduplication,
        "group_columns": ["split_group_date", "split_group_bundle", "split_group_case", "split_group_policy_date"],
    }
    dataset_info = save_dataset(
        dataset_root,
        family_hash,
        x_design.to_numpy(dtype=float),
        x_encoded.to_numpy(dtype=float),
        y_df.to_numpy(dtype=float),
        meta,
        bounds_names=list(numeric_feature_columns),
        target_names=list(target_columns),
        family_spec=family_spec,
        source_runs=_source_runs_manifest(selected=selected, skipped_duplicates=skipped_duplicates),
    )
    truth_csv_path = Path(dataset_info["truth_csv_path"])
    truth_meta_path = Path(dataset_info["truth_meta_path"])
    selected.to_csv(truth_csv_path, index=False)
    truth_meta_path.write_text(
        json.dumps(
            {
                "dataset_kind": "thermflex_hourly_dispatch_curated_truth",
                "family_hash": family_hash,
                "dataset_id": dataset_id,
                "rows_total_before_selection": int(len(truth)),
                "rows_after_selection": int(len(selected)),
                "selected_bundle_names": sorted(selected["source_bundle_name"].astype(str).unique().tolist()),
                "policy_hour_deduplication": policy_hour_deduplication,
                "raw_columns": list(selected.columns),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    settings_stub = SimpleNamespace(learning=SimpleNamespace(registry_path=str(registry_path)))
    register_dataset(
        settings_stub,
        family_hash,
        dataset_id,
        {
            "source": "thermflex_hourly_dispatch_curated",
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
        feature_columns=tuple(numeric_feature_columns),
        target_columns=tuple(target_columns),
    )


def _discover_under_root(*, root: Path, include_checkpoints: bool, min_checkpoint_rows: int) -> list[Path]:
    final_by_bundle = {path.parent.resolve(): path.resolve() for path in root.rglob(_FINAL_FILENAME)}
    selected = dict(final_by_bundle)
    if include_checkpoints:
        for checkpoint in sorted(root.rglob(_CHECKPOINT_FILENAME)):
            checkpoint = checkpoint.resolve()
            row_count = _count_csv_rows(checkpoint)
            if row_count < int(min_checkpoint_rows):
                continue
            final_path = checkpoint.parent / _FINAL_FILENAME
            bundle_dir = checkpoint.parent.resolve()
            if final_path.exists() and _count_csv_rows(final_path) >= row_count:
                continue
            selected[bundle_dir] = checkpoint
    return sorted(selected.values())


def _add_engineered_time_features(frame: pd.DataFrame) -> pd.DataFrame:
    df = frame.copy()
    hour = pd.to_numeric(df["hour_index"], errors="raise").to_numpy(dtype=float)
    day = df["timestamp"].dt.dayofyear.to_numpy(dtype=float)
    df["hour_of_day_sin"] = np.sin((2.0 * np.pi * hour) / 24.0)
    df["hour_of_day_cos"] = np.cos((2.0 * np.pi * hour) / 24.0)
    df["day_of_year_sin"] = np.sin((2.0 * np.pi * day) / 365.0)
    df["day_of_year_cos"] = np.cos((2.0 * np.pi * day) / 365.0)
    return df


@lru_cache(maxsize=1)
def _canonical_system_hourly_context() -> pd.DataFrame:
    context = load_vienna_dh_thermflex_full_year_context()
    columns = [
        "timestamp",
        "t_outdoor_c",
        "irradiance_proxy",
        "solargains_proxy",
        "dh_space_heat_total_kwh",
        "dh_hotwater_total_kwh",
        "dh_total_kwh",
        "mc_auction_eur_mwh",
        "gas_price_eur_mwh_fuel",
        "co2_price_eur_tco2",
    ]
    system_df = context.hourly_system_df.loc[:, columns].copy()
    system_df["timestamp"] = pd.to_datetime(system_df["timestamp"], errors="raise")
    return system_df


def _enrich_with_system_hourly_context(frame: pd.DataFrame) -> pd.DataFrame:
    context = _canonical_system_hourly_context()
    enriched = frame.merge(context, on="timestamp", how="left", validate="many_to_one")
    required = [column for column in context.columns if column != "timestamp"]
    missing = [column for column in required if enriched[column].isna().any()]
    if missing:
        raise ValueError(
            "[thermflex_hourly_dispatch] canonical system hourly-context enrichment missing columns: "
            + ", ".join(sorted(missing))
        )
    return enriched


def _validate_unique_hourly_keys(frame: pd.DataFrame) -> None:
    key_columns = ["source_bundle_name", "policy_case_label_canonical", "date", "hour_index"]
    duplicate_mask = frame.duplicated(subset=key_columns, keep=False)
    if duplicate_mask.any():
        examples = frame.loc[duplicate_mask, key_columns].head(10).to_dict(orient="records")
        raise ValueError(
            "[thermflex_hourly_dispatch] duplicate hourly truth keys found; examples="
            + json.dumps(examples, default=str)
        )


def _deduplicate_policy_hour_rows(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    key_columns = ["flex_override_name", "date", "hour_index"]
    compare_columns = tuple(feature_columns() + TARGET_COLUMNS)
    duplicate_mask = frame.duplicated(subset=key_columns, keep=False)
    if not duplicate_mask.any():
        return frame.copy(), {"dropped_rows": 0, "duplicate_policy_hour_groups": 0}

    duplicate_groups = frame.loc[duplicate_mask].groupby(key_columns, sort=True)
    conflicts: list[dict[str, Any]] = []
    for key, group in duplicate_groups:
        numeric = group.loc[:, list(compare_columns)].apply(pd.to_numeric, errors="raise").astype(float)
        spread = numeric.max(axis=0) - numeric.min(axis=0)
        conflict_columns = [column for column, value in spread.items() if float(abs(value)) > 1e-9]
        if conflict_columns:
            conflicts.append(
                {
                    "flex_override_name": str(key[0]),
                    "date": str(pd.Timestamp(key[1]).date()),
                    "hour_index": int(key[2]),
                    "conflict_columns": conflict_columns[:20],
                }
            )
    if conflicts:
        raise ValueError(
            "[thermflex_hourly_dispatch] duplicate policy-hour rows disagree; examples="
            + json.dumps(conflicts[:10], default=str)
        )

    selected = (
        frame.sort_values(["flex_override_name", "date", "hour_index", "source_bundle_name"])
        .drop_duplicates(subset=key_columns, keep="first")
        .reset_index(drop=True)
    )
    return selected, {
        "dropped_rows": int(len(frame) - len(selected)),
        "duplicate_policy_hour_groups": int(duplicate_groups.ngroups),
        "key_columns": key_columns,
        "rule": "drop_exact_duplicate_policy_hour_rows_keep_first_bundle_name",
    }


def _validate_complete_numeric_columns(frame: pd.DataFrame, *, columns: Sequence[str]) -> None:
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise KeyError("[thermflex_hourly_dispatch] missing feature/target columns: " + ", ".join(missing))
    numeric = frame.loc[:, list(columns)].apply(pd.to_numeric, errors="raise")
    null_columns = [column for column in numeric.columns if numeric[column].isna().any()]
    if null_columns:
        raise ValueError(
            "[thermflex_hourly_dispatch] feature/target columns contain missing values: "
            + ", ".join(null_columns)
        )


def _count_csv_rows(path: Path) -> int:
    with Path(path).open("r", encoding="utf-8-sig") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def _run_slug_from_bundle_name(bundle_name: str) -> str:
    prefix = "daily_thermflex_screen_"
    if not bundle_name.startswith(prefix):
        return ""
    stem = bundle_name[len(prefix) :]
    parts = stem.rsplit("_", 2)
    if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
        return parts[0]
    return stem


def _selected_bundle_signatures(frame: pd.DataFrame) -> list[dict[str, Any]]:
    signatures: list[dict[str, Any]] = []
    for bundle_name, group in frame.groupby("source_bundle_name", sort=True):
        signatures.append(
            {
                "source_bundle_name": str(bundle_name),
                "source_hourly_csv": str(group["source_hourly_csv"].iloc[0]),
                "source_hourly_kind": str(group["source_hourly_kind"].iloc[0]),
                "flex_case_label": str(group["flex_case_label"].iloc[0]),
                "flex_override_name": str(group["flex_override_name"].iloc[0]),
                "row_count": int(len(group)),
                "date_count": int(group["date"].dt.strftime("%Y-%m-%d").nunique()),
                "first_date": str(group["date"].min().date()),
                "last_date": str(group["date"].max().date()),
            }
        )
    return signatures


def _source_runs_manifest(
    *,
    selected: pd.DataFrame,
    skipped_duplicates: list[dict[str, str]],
) -> list[dict[str, Any]]:
    manifest = _selected_bundle_signatures(selected)
    if skipped_duplicates:
        manifest.append({"skipped_duplicates": skipped_duplicates})
    return manifest


def _hash_family_spec(family_spec: dict[str, Any]) -> str:
    payload = json.dumps(family_spec, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> None:
    result = export_curated_hourly_dispatch_dataset()
    print(
        json.dumps(
            {
                "family_hash": result.family_hash,
                "dataset_id": result.dataset_id,
                "dataset_root": str(result.dataset_root),
                "truth_rows": result.truth_rows,
                "selected_rows": result.selected_rows,
                "selected_bundle_count": result.selected_bundle_count,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
