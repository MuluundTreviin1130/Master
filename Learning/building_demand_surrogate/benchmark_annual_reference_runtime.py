"""Measure EnergyPlus teacher vs demand-surrogate wall-clock for one Vienna city year.

The comparison is the paper runtime claim: eight `annual_reference_2023` cohort
profiles from the existing EnergyPlus teacher path versus one inference of the
trained heating/cooling emulators on the same 8 x 8760 rows.

This script never writes into `_teacher_runs/`. EnergyPlus re-runs use a
temporary directory. SQL extraction reads the registered teacher SQLite files
read-only. Results are paper artifacts, not training truth.
"""

from __future__ import annotations

import json
import platform
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from Settings.technical.building_calibration import make_building_calibration_config
from Technical_model.technologies.buildings.calibration.teachers.energyplus import (
    _build_equivalent_geometry,
    _build_full_year_schedule_frame,
    _build_teacher_idf,
    _discover_energyplus,
    _extract_hourly_outputs,
    _resolve_teacher_context,
    _write_schedule_csv,
)
from Learning.building_demand_surrogate.train_annual_reference_demand_surrogate import (
    EXPERIMENT_ID,
    TARGETS,
    _load_dataset,
    _make_model,
)


# Paper-facing output lives in Documentation so it is not swallowed by the
# gitignored Learning/models and Learning/datasets trees.
PAPER_RESULTS_DIR = (
    REPOSITORY_ROOT
    / "Documentation"
    / "Papers"
    / "energyplus_demand_surrogate_vienna"
    / "results"
)
ENGINE_REPEATS = 3
SURROGATE_REPEATS = 5
REPEATED_EVALUATIONS = (1, 10, 50)
_EPLUS_END_ELAPSED_RE = re.compile(
    r"Elapsed Time=\s*(\d+)hr\s+(\d+)min\s+([0-9.]+)sec",
    re.IGNORECASE,
)


def _parse_eplus_end_elapsed_s(end_path: Path) -> float:
    """Parse EnergyPlus engine elapsed time from eplusout.end. Missing text is an error."""
    text = end_path.read_text(encoding="utf-8", errors="ignore")
    match = _EPLUS_END_ELAPSED_RE.search(text)
    if match is None:
        raise ValueError(f"[runtime_benchmark] Could not parse elapsed time from {end_path}: {text.strip()!r}")
    return (int(match.group(1)) * 3600.0) + (int(match.group(2)) * 60.0) + float(match.group(3))


def _median(values: list[float]) -> float:
    if not values:
        raise ValueError("[runtime_benchmark] Cannot take a median of an empty timing list.")
    return float(statistics.median(values))


def _teacher_experiment_dir(cfg, cohort_id: str) -> Path:
    path = Path(cfg.teacher_runs_output_dir).resolve() / cohort_id / EXPERIMENT_ID
    if not path.is_dir():
        raise FileNotFoundError(f"[runtime_benchmark] Missing teacher run directory: {path}")
    return path


def _require_teacher_file(directory: Path, name: str) -> Path:
    path = directory / name
    if not path.is_file():
        raise FileNotFoundError(f"[runtime_benchmark] Missing teacher file: {path}")
    return path


def _time_prepare_s(*, cohort_id: str, cfg, scratch: Path) -> float:
    """Time schedule + IDF construction, the Python side of a new teacher evaluation."""
    cohort, experiment = _resolve_teacher_context(cohort_id=cohort_id, experiment_id=EXPERIMENT_ID)
    workdir = scratch / "prepare" / cohort_id
    workdir.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    schedule_df = _build_full_year_schedule_frame(
        calendar_year=int(experiment["calendar_year"]),
        cohort=cohort,
        experiment=experiment,
    )
    schedule_csv_path = _write_schedule_csv(workdir, schedule_df=schedule_df)
    geometry = _build_equivalent_geometry(cohort)
    _build_teacher_idf(
        idf_path=workdir / "teacher_experiment.idf",
        cohort=cohort,
        experiment=experiment,
        geometry=geometry,
        schedule_csv_path=schedule_csv_path,
        year_rows=len(schedule_df),
        version=str(cfg.energyplus_idf_version),
    )
    return time.perf_counter() - started


def _time_energyplus_engine(*, cohort_id: str, cfg, scratch: Path) -> tuple[list[float], list[float]]:
    """Re-run the registered IDF in a temp dir. Does not touch the SSOT teacher folder."""
    source = _teacher_experiment_dir(cfg, cohort_id)
    idf_src = _require_teacher_file(source, "teacher_experiment.idf")
    schedule_src = _require_teacher_file(source, "teacher_schedules.csv")
    _, experiment = _resolve_teacher_context(cohort_id=cohort_id, experiment_id=EXPERIMENT_ID)
    epw_path = Path(experiment["epw_path"]).resolve()
    if not epw_path.is_file():
        raise FileNotFoundError(f"[runtime_benchmark] Missing EPW for '{cohort_id}': {epw_path}")
    exe = _discover_energyplus(cfg.energyplus_executable_path)
    wall_times: list[float] = []
    engine_times: list[float] = []
    for repeat in range(ENGINE_REPEATS):
        workdir = scratch / "engine" / cohort_id / f"repeat_{repeat}"
        workdir.mkdir(parents=True, exist_ok=False)
        shutil.copy2(idf_src, workdir / "teacher_experiment.idf")
        shutil.copy2(schedule_src, workdir / "teacher_schedules.csv")
        command = (
            str(exe),
            "-w",
            str(epw_path),
            "-d",
            str(workdir),
            str(workdir / "teacher_experiment.idf"),
        )
        started = time.perf_counter()
        proc = subprocess.run(command, cwd=str(workdir), capture_output=True, text=True, check=False)
        wall_s = time.perf_counter() - started
        if proc.returncode != 0:
            raise RuntimeError(
                f"[runtime_benchmark] EnergyPlus re-run failed for '{cohort_id}' repeat {repeat}: {proc.stderr}"
            )
        wall_times.append(wall_s)
        engine_times.append(_parse_eplus_end_elapsed_s(workdir / "eplusout.end"))
    return wall_times, engine_times


def _time_sql_extract_s(*, cohort_id: str, cfg) -> float:
    """Time the SQL-to-hourly conversion that turns an EnergyPlus run into demand rows."""
    source = _teacher_experiment_dir(cfg, cohort_id)
    sql_path = _require_teacher_file(source, "eplusout.sql")
    _, experiment = _resolve_teacher_context(cohort_id=cohort_id, experiment_id=EXPERIMENT_ID)
    started = time.perf_counter()
    hourly = _extract_hourly_outputs(sql_path, control_mode=str(experiment["control_mode"]))
    if hourly.empty:
        raise ValueError(f"[runtime_benchmark] Empty hourly extract for '{cohort_id}'.")
    return time.perf_counter() - started


def _time_surrogate() -> dict[str, object]:
    """Fit the published estimator in-process and time inference on 8 x 8760 rows.

    The registered `joblib` files unpickle with a numpy RNG ABI error in this
    interpreter. Holdout accuracy stays in `model_manifest.json`. Runtime uses
    `_make_model()` on the same teacher table, fitted here so EnergyPlus and
    inference share one process.
    """
    load_data_started = time.perf_counter()
    data, features = _load_dataset()
    load_data_s = time.perf_counter() - load_data_started
    if int(data["cohort_id"].nunique()) != 8 or len(data) != 8 * 8760:
        raise ValueError("[runtime_benchmark] Surrogate feature table is not eight complete annual cohort runs.")

    matrix_started = time.perf_counter()
    x = data.loc[:, features].to_numpy(dtype=float)
    matrix_s = time.perf_counter() - matrix_started
    models: dict[str, object] = {}
    fit_times: dict[str, float] = {}
    for target in TARGETS:
        y = data[target].to_numpy(dtype=float)
        model = _make_model()
        started = time.perf_counter()
        model.fit(x, y)
        fit_times[target] = time.perf_counter() - started
        models[target] = model
    train_s = float(sum(fit_times.values()))

    def _predict_both() -> None:
        for model in models.values():
            prediction = np.asarray(model.predict(x), dtype=float)
            if prediction.shape != (len(data),):
                raise ValueError("[runtime_benchmark] Surrogate prediction length does not match the feature table.")

    _predict_both()
    predict_times = []
    for _ in range(SURROGATE_REPEATS):
        started = time.perf_counter()
        _predict_both()
        predict_times.append(time.perf_counter() - started)
    return {
        "n_rows": int(len(data)),
        "n_cohorts": int(data["cohort_id"].nunique()),
        "inference_source": "in_process_refit_same_estimator_and_teacher_table",
        "load_feature_table_s": load_data_s,
        "feature_matrix_s": matrix_s,
        "fit_per_target_s": fit_times,
        "fit_both_targets_s": train_s,
        "predict_both_targets_repeats_s": predict_times,
        "predict_both_targets_median_s": _median(predict_times),
        "cohort_ids": sorted(str(item) for item in data["cohort_id"].unique()),
    }


def _write_markdown(summary: dict[str, object], out_path: Path) -> None:
    city = summary["city_year"]
    surrogate = summary["surrogate"]
    lines = [
        "# EnergyPlus vs demand-surrogate runtime",
        "",
        "One Vienna city year is eight `annual_reference_2023` cohort profiles (8 x 8760 h).",
        "Diagnostic plots are excluded. EnergyPlus re-runs used a temporary directory and did not overwrite `_teacher_runs/`.",
        "Surrogate inference was timed on an in-process refit of the published HistGradientBoosting spec; holdout accuracy remains `model_manifest.json`.",
        "",
        f"- Host: `{summary['host']['node']}` / `{summary['host']['machine']}` / `{summary['host']['processor']}`",
        f"- Python: `{summary['host']['python']}`",
        f"- EnergyPlus engine repeats per cohort: `{ENGINE_REPEATS}`",
        f"- Surrogate predict repeats: `{SURROGATE_REPEATS}`",
        "",
        "| Quantity | Seconds |",
        "|---|---:|",
        f"| EnergyPlus prepare (schedules + IDF), 8 cohorts | {city['prepare_s']:.3f} |",
        f"| EnergyPlus engine wall-clock median sum, 8 cohorts | {city['energyplus_wall_median_sum_s']:.3f} |",
        f"| EnergyPlus engine `eplusout.end` median sum, 8 cohorts | {city['energyplus_end_median_sum_s']:.3f} |",
        f"| EnergyPlus SQL extract, 8 cohorts | {city['sql_extract_s']:.3f} |",
        f"| EnergyPlus demand-path total (prepare + engine wall + extract) | {city['demand_path_s']:.3f} |",
        f"| Surrogate load feature table | {surrogate['load_feature_table_s']:.3f} |",
        f"| Surrogate fit both targets, one-time | {surrogate['fit_both_targets_s']:.3f} |",
        f"| Surrogate predict both targets, median | {surrogate['predict_both_targets_median_s']:.4f} |",
        f"| Speedup, demand-path / predict | {city['speedup_demand_path_vs_predict']:.1f} |",
        f"| Speedup, engine wall / predict | {city['speedup_engine_wall_vs_predict']:.1f} |",
        "",
        "Repeated city-year evaluations after the surrogate is already loaded:",
        "",
        "| Evaluations | EnergyPlus demand-path [s] | Surrogate predict [s] | Time saved [s] |",
        "|---:|---:|---:|---:|",
    ]
    for row in summary["repeated_evaluations"]:
        lines.append(
            f"| {row['n_evaluations']} | {row['energyplus_demand_path_s']:.3f} | "
            f"{row['surrogate_predict_s']:.4f} | {row['time_saved_s']:.3f} |"
        )
    lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    cfg = make_building_calibration_config()
    teacher_root = Path(cfg.teacher_runs_output_dir).resolve()
    if not teacher_root.is_dir():
        raise FileNotFoundError(f"[runtime_benchmark] Teacher output root missing: {teacher_root}")

    data, _features = _load_dataset()
    cohort_ids = sorted(str(item) for item in data["cohort_id"].unique())
    if len(cohort_ids) != 8:
        raise ValueError(
            f"[runtime_benchmark] Expected exactly eight registered Vienna cohorts, got {cohort_ids}."
        )

    PAPER_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    cohort_rows: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="eplus_demand_runtime_") as scratch_name:
        scratch = Path(scratch_name)
        if teacher_root in scratch.parents or scratch == teacher_root:
            raise RuntimeError("[runtime_benchmark] Refusing to use the SSOT teacher directory as scratch.")
        for cohort_id in cohort_ids:
            archived_end = _parse_eplus_end_elapsed_s(_require_teacher_file(_teacher_experiment_dir(cfg, cohort_id), "eplusout.end"))
            prepare_s = _time_prepare_s(cohort_id=cohort_id, cfg=cfg, scratch=scratch)
            wall_times, engine_times = _time_energyplus_engine(cohort_id=cohort_id, cfg=cfg, scratch=scratch)
            extract_s = _time_sql_extract_s(cohort_id=cohort_id, cfg=cfg)
            row = {
                "cohort_id": cohort_id,
                "archived_eplusout_end_s": archived_end,
                "prepare_s": prepare_s,
                "energyplus_wall_repeats_s": wall_times,
                "energyplus_wall_median_s": _median(wall_times),
                "energyplus_end_repeats_s": engine_times,
                "energyplus_end_median_s": _median(engine_times),
                "sql_extract_s": extract_s,
                "demand_path_s": prepare_s + _median(wall_times) + extract_s,
            }
            cohort_rows.append(row)
            print(
                f"[runtime_benchmark] {cohort_id}: demand_path={row['demand_path_s']:.3f}s "
                f"(prepare={prepare_s:.3f}, engine_wall={row['energyplus_wall_median_s']:.3f}, extract={extract_s:.3f})"
            )
        checkpoint_path = PAPER_RESULTS_DIR / "runtime_benchmark_energyplus_checkpoint.json"
        checkpoint_path.write_text(json.dumps(cohort_rows, indent=2), encoding="utf-8")

    surrogate = _time_surrogate()
    if surrogate["cohort_ids"] != cohort_ids:
        raise ValueError("[runtime_benchmark] Surrogate cohort set does not match the teacher benchmark set.")

    prepare_sum = float(sum(float(row["prepare_s"]) for row in cohort_rows))
    engine_wall_sum = float(sum(float(row["energyplus_wall_median_s"]) for row in cohort_rows))
    engine_end_sum = float(sum(float(row["energyplus_end_median_s"]) for row in cohort_rows))
    extract_sum = float(sum(float(row["sql_extract_s"]) for row in cohort_rows))
    demand_path_s = prepare_sum + engine_wall_sum + extract_sum
    predict_s = float(surrogate["predict_both_targets_median_s"])
    if predict_s <= 0.0:
        raise ValueError("[runtime_benchmark] Surrogate predict time must be > 0.")
    city = {
        "n_cohorts": 8,
        "hours_per_cohort": 8760,
        "prepare_s": prepare_sum,
        "energyplus_wall_median_sum_s": engine_wall_sum,
        "energyplus_end_median_sum_s": engine_end_sum,
        "sql_extract_s": extract_sum,
        "demand_path_s": demand_path_s,
        "speedup_demand_path_vs_predict": demand_path_s / predict_s,
        "speedup_engine_wall_vs_predict": engine_wall_sum / predict_s,
        "time_saved_one_city_year_s": demand_path_s - predict_s,
    }
    repeated = []
    for n_eval in REPEATED_EVALUATIONS:
        eplus_s = n_eval * demand_path_s
        surrogate_s = n_eval * predict_s
        repeated.append(
            {
                "n_evaluations": n_eval,
                "energyplus_demand_path_s": eplus_s,
                "surrogate_predict_s": surrogate_s,
                "time_saved_s": eplus_s - surrogate_s,
            }
        )
    summary = {
        "schema_version": "vienna_building_demand_runtime_benchmark_v1",
        "experiment_id": EXPERIMENT_ID,
        "scope": (
            "Wall-clock comparison of the EnergyPlus teacher demand path against "
            "HistGradientBoosting inference for the eight registered Vienna cohorts. "
            "No building flexibility, no PyPSA, no diagnostic plots."
        ),
        "host": {
            "node": platform.node(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python": sys.version.split()[0],
        },
        "protocol": {
            "engine_repeats": ENGINE_REPEATS,
            "surrogate_predict_repeats": SURROGATE_REPEATS,
            "energyplus_scratch": "tempfile, copies of registered IDF and schedules",
            "ssot_teacher_runs_modified": False,
            "plots_included": False,
        },
        "cohorts": cohort_rows,
        "surrogate": surrogate,
        "city_year": city,
        "repeated_evaluations": repeated,
    }
    json_path = PAPER_RESULTS_DIR / "runtime_benchmark.json"
    csv_path = PAPER_RESULTS_DIR / "runtime_benchmark.csv"
    md_path = PAPER_RESULTS_DIR / "runtime_benchmark.md"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    csv_rows = [
        {key: value for key, value in row.items() if not str(key).endswith("_repeats_s")}
        for row in cohort_rows
    ]
    pd.DataFrame(csv_rows).to_csv(csv_path, index=False)
    _write_markdown(summary, md_path)
    checkpoint_path = PAPER_RESULTS_DIR / "runtime_benchmark_energyplus_checkpoint.json"
    if checkpoint_path.exists():
        checkpoint_path.unlink()
    print(f"[runtime_benchmark] demand_path_city={demand_path_s:.3f}s predict={predict_s:.4f}s speedup={city['speedup_demand_path_vs_predict']:.1f}x")
    print(f"[runtime_benchmark] wrote {json_path}")


if __name__ == "__main__":
    main()
