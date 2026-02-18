# Optimization/validation/teachers/call_rowwise.py
from __future__ import annotations

from typing import Tuple
import numpy as np
import pandas as pd

from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.validation.engines.params_mapping import get_param_aliases, build_kwargs_for_row


def call_rowwise(sim_fn, X: pd.DataFrame, S) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Row-wise Call mit Parametermapping über Settings-Aliases.
    Rückgabe: (Flows-DF, KPI-DF).
    """
    aliases = get_param_aliases(S)

    flow_rows = []
    kpi_rows = []
    first_flow_dim = None
    first_kpi_dim = None

    for idx, row in X.iterrows():
        row_dict = row.to_dict()
        kwargs = build_kwargs_for_row(sim_fn, row_dict, S, aliases)
        out = sim_fn(**kwargs)

        if isinstance(out, tuple) and len(out) == 2:
            f, k = out
        else:
            f, k = out, None

        f_arr = np.atleast_1d(np.asarray(f, dtype=float))
        if first_flow_dim is None:
            first_flow_dim = f_arr.shape[0]
        elif f_arr.shape[0] != first_flow_dim:
            raise ValueError("[teacher] inkonsistente Fluss-Dimension im row-wise Call")
        flow_rows.append(f_arr)

        if k is not None:
            k_arr = np.atleast_1d(np.asarray(k, dtype=float))
            if first_kpi_dim is None:
                first_kpi_dim = k_arr.shape[0]
            elif k_arr.shape[0] != first_kpi_dim:
                raise ValueError("[teacher] inkonsistente KPI-Dimension im row-wise Call")
            kpi_rows.append(k_arr)

    flows = np.vstack(flow_rows) if flow_rows else np.empty((0, 0), dtype=float)
    kpis = np.vstack(kpi_rows) if kpi_rows else None

    F = pd.DataFrame(flows, index=X.index)
    K = pd.DataFrame(kpis, index=X.index) if kpis is not None else pd.DataFrame(index=X.index)
    return F, K
