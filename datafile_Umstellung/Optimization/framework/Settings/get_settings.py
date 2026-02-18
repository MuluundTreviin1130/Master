from __future__ import annotations

from .settings_model import Settings

from .run import make_run
from .engine import make_engine
from .bounds import make_bounds
from .objectives import make_objectives
from .constraints import make_constraints
from .sampler import make_sampler
from .optimizer import make_optimizer
from .reporting import make_reporting
from .surrogate_train import make_surrogate_train
from .gating import make_gating
from .validation import make_validation

# --- one-time startup diagnostics (set False to silence) ---
PRINT_STARTUP_SNAPSHOT = True
SNAPSHOT_METRIC = "climate_change"
SNAPSHOT_TECHS = ("PV", "BESS", "Grid")


def _safe_get(dct, *keys, default=None):
    cur = dct
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def get_settings() -> Settings:
    engine = make_engine()

    # lifetime_years is required for PB scaling. Prefer Data.params if available.
    lifetime_years = 25
    params = None

    try:
        from Data.params import get_parameters
        params = get_parameters(engine.location)
        lifetime_years = int(params.get("lifetime", lifetime_years))
        source = "Data.params.get_parameters"
    except Exception as e:
        try:
            from Data.data import get_parameters
            params = get_parameters(engine.location)
            lifetime_years = int(params.get("lifetime", lifetime_years))
            source = "Data.data.get_parameters (legacy)"
        except Exception:
            source = "NO get_parameters available"

    bounds = make_bounds(engine)
    objectives = make_objectives()
    constraints = make_constraints(engine, lifetime_years=lifetime_years)
    sampler = make_sampler()
    optimizer = make_optimizer()
    reporting = make_reporting()
    surrogate_train = make_surrogate_train()
    gating = make_gating()
    validation = make_validation()

    if PRINT_STARTUP_SNAPSHOT:
        print(f"[SETTINGS] parameters source: {source}")
        print(f"[SETTINGS] lifetime_years: {lifetime_years}")

        # LCA snapshot (once)
        if isinstance(params, dict):
            print(f"[LCA SNAPSHOT] metric={SNAPSHOT_METRIC}")
            for tech in SNAPSHOT_TECHS:
                infra = _safe_get(params, tech, "LCA", "infra", default={}).get(SNAPSHOT_METRIC)
                op = _safe_get(params, tech, "LCA", "op", default={}).get(SNAPSHOT_METRIC)
                print(f"  - {tech}: infra={infra} | op={op}")
        else:
            print("[LCA SNAPSHOT] params not available (no get_parameters call succeeded)")

        # Objectives / constraints snapshot (once)
        obj_names = getattr(objectives, "names", None)
        con_names = getattr(constraints, "names", None)
        print(f"[OBJECTIVES] names={obj_names}")
        print(f"[CONSTRAINTS] names={con_names}")

        # Optimierungsalgorithmus anzeigen
        opt_name = getattr(optimizer, "name", "unknown")
        print(f"[OPTIMIZER] algorithm: {opt_name}")

    try:
        return Settings(
            run=make_run(),
            engine=engine,
            bounds=bounds,
            objectives=objectives,
            constraints=constraints,
            sampler=sampler,
            optimizer=optimizer,
            reporting=reporting,
            surrogate_train=surrogate_train,
            gating=gating,
            validation=validation,
        )
    except TypeError as exc:
        # Backward compatibility: older Settings without "validation"
        if "validation" not in str(exc):
            raise
        s = Settings(
            run=make_run(),
            engine=engine,
            bounds=bounds,
            objectives=objectives,
            constraints=constraints,
            sampler=sampler,
            optimizer=optimizer,
            reporting=reporting,
            surrogate_train=surrogate_train,
            gating=gating,
        )
        setattr(s, "validation", validation)
        return s
