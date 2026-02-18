from __future__ import annotations

from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.framework.Settings import settings as settings_mod
from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.framework.Settings.settings import get_settings


def get_settings_with_validation():
    """
    Holt das zentrale Settings-Objekt und hängt die Validation-/Paths-Blöcke
    aus dem Settings-Modul an, falls vorhanden.
    """
    S = get_settings()

    validation_cfg = getattr(settings_mod, "validation", None)
    if validation_cfg is not None and not hasattr(S, "validation"):
        setattr(S, "validation", validation_cfg)

    paths_cfg = getattr(settings_mod, "paths", None)
    if paths_cfg is not None and not hasattr(S, "paths"):
        setattr(S, "paths", paths_cfg)

    return S
