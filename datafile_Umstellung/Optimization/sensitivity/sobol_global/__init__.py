# Optimization/sensitivity/sobol_global/__init__.py
"""
Globale Sobol-Sensitivitätsanalyse auf Basis des trainierten Surrogats.

Aktueller Fokus:
- Design-Sensitivität: Bounds aus settings.bounds (z.B. pv_kwp, bess_kwh)
- Auswertung eines existierenden Surrogat-Artefakts (surrogate_rf.joblib)
- Kopplung an settings.run.tag und settings.reporting.output_root

Später erweiterbar auf:
- zusätzliche Unsicherheitsparameter (Preise, CAPEX, EV-Verhalten, Wetter, ...)
- robustere Zielgrößen (z.B. Erwartungswerte über Szenarien).
"""
