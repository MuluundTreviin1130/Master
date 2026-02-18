# Optimization/run/run_optimization.py
"""
Haupt-Script zur Durchführung einer Optimierung.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Workspace-Root finden - suche nach V2H_energy_community_surrogat_datafilenew Ordner
current = Path(__file__).resolve()
workspace_root = None
datafile_umstellung_dir = None

# Suche nach dem Workspace-Root (enthält V2H_energy_community_surrogat_datafilenew)
for parent in current.parents:
    v2h_dir = parent / "V2H_energy_community_surrogat_datafilenew"
    if v2h_dir.exists():
        workspace_root = parent
        datafile_umstellung_dir = v2h_dir / "datafile_Umstellung"
        break

if workspace_root is None:
    # Fallback: verwende die alte Methode
    workspace_root = current.parent.parent.parent.parent.parent
    datafile_umstellung_dir = workspace_root / "V2H_energy_community_surrogat_datafilenew" / "datafile_Umstellung"

# Beide Pfade hinzufügen:
# 1. Workspace-Root (für vollständige Imports)
workspace_root_str = str(workspace_root.resolve())
if workspace_root_str not in sys.path:
    sys.path.insert(0, workspace_root_str)

# 2. datafile_Umstellung (für relative Imports wie Optimization.framework...)
# WICHTIG: Dieser muss VOR allen Imports gesetzt sein, damit Data und Technical_model gefunden werden
if datafile_umstellung_dir and datafile_umstellung_dir.exists():
    datafile_umstellung_str = str(datafile_umstellung_dir.resolve())
    if datafile_umstellung_str not in sys.path:
        sys.path.insert(0, datafile_umstellung_str)
else:
    raise RuntimeError(
        f"[run_optimization] datafile_Umstellung Ordner nicht gefunden!\n"
        f"  Gesucht in: {workspace_root / 'V2H_energy_community_surrogat_datafilenew' / 'datafile_Umstellung'}\n"
        f"  Aktuelles Verzeichnis: {Path.cwd()}\n"
        f"  Script-Pfad: {current}"
    )

from Optimization.framework.Settings.get_settings import get_settings
from Optimization.framework.Orchestrator.optimize import run

import time

if __name__ == "__main__":
    s = get_settings()       # EINZIGE Quelle der Wahrheit

    t0 = time.perf_counter()           # Startzeit
    result = run(s)
    t1 = time.perf_counter()           # Endzeit

    total_s = t1 - t0
    print("Run fertig. Ergebnisse:", result.get("run_dir"))
    print(f"[timing] total_run_s = {total_s:.2f} s")
