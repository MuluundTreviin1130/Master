from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from Documentation.Papers.thermflex_paper.tables.build_table_09_heating_season_kpis import (
    build_table_09_heating_season_kpis,
)
from Learning.thermflex_daily_results.predict import predict_daily_results


@dataclass(frozen=True)
class SurrogateTable09Result:
    surrogate_screen_csv: Path
    output_md: Path
    output_csv: Path


def build_surrogate_table_09(
    *,
    template_screen_csv: Path | str,
    model_dir: Path | str,
    flex_override_name: str,
    flex_case_label: str | None = None,
    surrogate_screen_csv: Path | str,
    output_md: Path | str,
    output_csv: Path | str,
) -> SurrogateTable09Result:
    """
    Predict one surrogate heating-season day screen and pass it into the existing Table-09 builder.

    This keeps the paper table logic unchanged. Only the daily screen source is
    replaced by a surrogate-generated screen.
    """

    predicted = predict_daily_results(
        template_screen_csv=template_screen_csv,
        model_dir=model_dir,
        flex_override_name=flex_override_name,
        flex_case_label=flex_case_label,
    )
    surrogate_screen_path = Path(surrogate_screen_csv).resolve()
    output_md_path = Path(output_md).resolve()
    output_csv_path = Path(output_csv).resolve()
    surrogate_screen_path.parent.mkdir(parents=True, exist_ok=True)
    output_md_path.parent.mkdir(parents=True, exist_ok=True)
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    predicted.prediction_frame.to_csv(surrogate_screen_path, index=False)
    build_table_09_heating_season_kpis(
        screen_csv=surrogate_screen_path,
        output_md=output_md_path,
        output_csv=output_csv_path,
    )
    return SurrogateTable09Result(
        surrogate_screen_csv=surrogate_screen_path,
        output_md=output_md_path,
        output_csv=output_csv_path,
    )
