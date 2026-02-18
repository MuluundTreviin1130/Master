from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class SurrogateTrainConfig:
    model_type: str = "rf"
    rf_n_estimators: int = 500
    rf_n_jobs: int = -4
    holdout_frac: float = 0.2
    targets: List[str] = field(default_factory=list)
    include_objectives: bool = False
    
    # Feature configuration for signature building
    feature_names: List[str] = field(default_factory=lambda: [
        "pv_kwp",
        "bess_kwh",
        "system_id",
        "profile_id",
        "N_EV_total",
        "N_EV_bidirectional",
    ])
    feature_encoding: Dict[str, str] = field(default_factory=lambda: {
        "system_id": "hash32",
        "profile_id": "hash32"
    })
    
    # Teacher evaluation parallelization
    teacher_backend: str = "processes"  # "processes", "threads", or "none"
    teacher_n_workers: int = 0  # 0 => auto (cpu_count()-1)
    teacher_batch_size: int = 32


def make_surrogate_train() -> SurrogateTrainConfig:
    """Default surrogate training config.
    
    Empfehlungen für bessere Qualität:
    - rf_n_estimators: 300-600 für gute Qualität (mehr = besser, aber langsamer)
    - holdout_frac: 0.2 ist Standard (20% für Validierung)
    - teacher_n_workers: 0 = auto (nutzt alle CPUs - 1)
    """
    return SurrogateTrainConfig(
        model_type="rf",
        rf_n_estimators=400,  # Erhöht von 200 auf 400 für bessere Qualität
        rf_n_jobs=-1,
        holdout_frac=0.2,
        targets=[
          "E_import_grid_kWh",
          "E_export_grid_kWh",
          "E_import_ec_pv_kWh",
          "E_import_ec_ev_kWh",
          "E_export_ec_pv_kWh",
          "E_total_load_kWh",
          "PV_generation_kWh",
        ],
        include_objectives=True,
        feature_names=[
            "pv_kwp",
            "bess_kwh",
            "system_id",
            "profile_id",
            "N_EV_total",
            "N_EV_bidirectional",
        ],
        feature_encoding={
            "system_id": "hash32",
            "profile_id": "hash32"
        },
        teacher_backend="processes",
        teacher_n_workers=0,
        teacher_batch_size=32,
    )
