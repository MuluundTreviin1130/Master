import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Data/data.py als Paket importieren
from Data import data as data
from Technical_model.consumption.heating_anc_cooling_consumption.heating_control import (
    active_cooling_enabled,
    active_heating_setpoint_k,
    cooling_setpoint_k,
    design_indoor_temp_k,
    design_internal_gains_w_per_m2,
    design_outdoor_temp_k,
    design_solar_gains_w_per_m2,
    design_ventilation_mode,
    heating_hysteresis_bounds_k,
    heating_power_mode,
    max_cooling_energy_wh,
    max_heating_energy_wh,
    max_heating_power_multiplier,
)


def _design_total_air_change_per_h(usage_df, heating_control):
    ach_v = usage_df["Luftwechsel_Anlage_1_h"].to_numpy(dtype=float)
    ach_i = usage_df["Luftwechsel_Infiltration_1_h"].to_numpy(dtype=float)
    total_ach = ach_v + ach_i
    mode = design_ventilation_mode(heating_control)
    if mode == "mean":
        return float(np.mean(total_ach))
    if mode == "p95":
        return float(np.percentile(total_ach, 95))
    return float(np.max(total_ach))


def _effective_transmission_loss_coefficient_w_per_k(building_params):
    if "effective_transmission_loss_coefficient_w_per_k" not in building_params:
        raise KeyError(
            "[heating_and_cooling] building_params must contain 'effective_transmission_loss_coefficient_w_per_k'."
        )
    return float(building_params["effective_transmission_loss_coefficient_w_per_k"])


def _effective_air_loss_scale(building_params):
    if "effective_air_loss_scale" not in building_params:
        raise KeyError("[heating_and_cooling] building_params must contain 'effective_air_loss_scale'.")
    value = float(building_params["effective_air_loss_scale"])
    if value < 0.0:
        raise ValueError(f"[heating_and_cooling] effective_air_loss_scale must be >= 0, got {value}.")
    return value


def derive_design_heating_power_w_per_m2(building_params, usage_df, heating_control):
    cp_air = float(building_params["cp_air"])
    room_height = float(building_params["room_height"])
    a_floor = float(building_params["A_floor"])
    if a_floor <= 0.0:
        raise ValueError("[heating_and_cooling] A_floor must be > 0 for design heating power derivation.")

    l_t = _effective_transmission_loss_coefficient_w_per_k(building_params)

    delta_t = max(0.0, design_indoor_temp_k(heating_control) - design_outdoor_temp_k(heating_control))
    q_t = (l_t * delta_t) / a_floor
    ach_total = _design_total_air_change_per_h(usage_df, heating_control)
    q_v = ach_total * room_height * cp_air * delta_t * _effective_air_loss_scale(building_params)
    q_gains = design_internal_gains_w_per_m2(heating_control) + design_solar_gains_w_per_m2(heating_control)
    q_design = max(0.0, q_t + q_v - q_gains)
    return float(q_design * max_heating_power_multiplier(heating_control))


def calculate_dynamic_heating_cooling(T_outdoor, solar_gains, building_params, usage_df, heating_control=None):
    # --- Gebäudeeigenschaften ---
    cp_air = building_params["cp_air"]          # [Wh/m³K]
    room_height = building_params["room_height"]
    A_floor = building_params["A_floor"]
    if float(A_floor) <= 0.0:
        raise ValueError("[heating_and_cooling] A_floor must be > 0 for dynamic heating/cooling calculation.")
    heat_capacity = float(building_params["heat_capacity"])  # [Wh/K]
    if heating_control is None:
        raise ValueError(
            "[heating_and_cooling] heating_control settings are required. No legacy fallback is allowed."
        )
    cooling_setpoint = cooling_setpoint_k(heating_control)

    # --- Nutzungsprofile ---
    QI_winter = usage_df["Qi Winter W/m2"].to_numpy()
    QI_summer = usage_df["Qi Sommer W/m2"].to_numpy()
    ACH_V = usage_df["Luftwechsel_Anlage_1_h"].to_numpy()
    ACH_I = usage_df["Luftwechsel_Infiltration_1_h"].to_numpy()

    # --- Effektive Verlustparameter ---
    L_T = _effective_transmission_loss_coefficient_w_per_k(building_params)  # [W/K]
    air_loss_scale = _effective_air_loss_scale(building_params)

    # --- Initialisierung ---
    n_steps = len(T_outdoor)
    TI = np.zeros(n_steps)
    QT = np.zeros(n_steps)
    QV = np.zeros(n_steps)
    QI = np.zeros(n_steps)
    QS = np.zeros(n_steps)
    # These arrays are exported as specific hourly energy demand in kWh/m².
    # The actual control action QH/QC below is computed on whole-building level
    # in Wh because heat_capacity is a whole-building Wh/K value.
    #
    # That means the export must divide by BOTH:
    # - 1000 to convert Wh -> kWh
    # - A_floor to convert whole-building energy -> specific energy per m²
    #
    # Without the A_floor division, downstream helpers multiply by A_floor once
    # more and silently inflate heating/cooling demand by the full cohort floor
    # area. That was the root cause behind the absurd grid-import, cost and CO2
    # magnitudes in the Vienna paper slice.
    heating_load = np.zeros(n_steps)
    cooling_load = np.zeros(n_steps)
    TI[0] = active_heating_setpoint_k(0, heating_control)
    heating_on = False
    heating_power_cap_mode = heating_power_mode(heating_control)
    if heating_power_cap_mode == "archetype_design":
        resolved_max_heating_power_w_per_m2 = derive_design_heating_power_w_per_m2(
            building_params=building_params,
            usage_df=usage_df,
            heating_control=heating_control,
        )
    else:
        resolved_max_heating_power_w_per_m2 = float(heating_control.max_heating_power_w_per_m2)
    resolved_max_heating_energy_wh = float(max(0.0, resolved_max_heating_power_w_per_m2) * A_floor)
    dt_h = 1.0

    # Heiz-/Kühlflags bestimmen
    daily_avg_temp, heating_days, cooling_days, heating_flags, cooling_flags = analyze_heating_cooling_days(T_outdoor)

    # --- Simulation ---
    for t in range(1, n_steps):
        # Verluste und Gewinne berechnen
        dT = TI[t-1] - T_outdoor[t]
        qt_w = L_T * dT
        qv_w_per_m2 = ((ACH_I[t] + ACH_V[t]) * room_height * cp_air * dT) * air_loss_scale
        qv_w = qv_w_per_m2 * A_floor
        qi_w_per_m2 = QI_winter[t] if heating_flags[t] else QI_summer[t]
        qi_w = qi_w_per_m2 * A_floor
        qs_w_per_m2 = solar_gains[t]
        qs_w = qs_w_per_m2 * A_floor

        QT[t] = qt_w / A_floor
        QV[t] = qv_w_per_m2
        QI[t] = qi_w_per_m2
        QS[t] = qs_w_per_m2

        # Temperatur nach Verlusten/Gewinnen
        q_net_wh = (-qt_w - qv_w + qi_w + qs_w) * dt_h
        TI[t] = TI[t-1] + q_net_wh / heat_capacity

        setpoint_k = active_heating_setpoint_k(t % 24, heating_control)
        lower_k, upper_k = heating_hysteresis_bounds_k(setpoint_k, heating_control)
        if TI[t] < lower_k:
            heating_on = True
        elif TI[t] >= upper_k:
            heating_on = False

        if heating_on and TI[t] < upper_k:
            QH = min(
                max(0.0, (upper_k - TI[t]) * heat_capacity),
                resolved_max_heating_energy_wh,
            )
            heating_load[t] = QH / (1000.0 * A_floor)
            TI[t] = min(upper_k, TI[t] + QH / heat_capacity)

        if active_cooling_enabled(heating_control) and TI[t] > cooling_setpoint:
            QC = min(
                max(0.0, (TI[t] - cooling_setpoint) * heat_capacity),
                max_cooling_energy_wh(A_floor, 1.0, heating_control),
            )
            cooling_load[t] = abs(QC) / (1000.0 * A_floor)
            TI[t] = max(cooling_setpoint, TI[t] - QC / heat_capacity)

    # DataFrame erstellen (alle relevanten Größen wie im EnergyModel)
    df_hourly = pd.DataFrame({
        "T_innen [°C]": TI - 273.15,
        "T_außen [°C]": T_outdoor - 273.15,
        "QT [W/m²]": QT,
        "QV [W/m²]": QV,
        "QI [W/m²]": QI,
        "QS [W/m²]": QS,
        "Q_design_heat_max [W/m²]": np.full(n_steps, resolved_max_heating_power_w_per_m2, dtype=float),
        "Heizlast [kWh/m²]": heating_load,
        "Kühllast [kWh/m²]": cooling_load
    })

    return df_hourly



def analyze_heating_cooling_days(T_outdoor, heating_threshold=285.15, cooling_threshold=291.45):
    daily_avg_temp = T_outdoor.reshape(-1, 24).mean(axis=1)
    heating_days = daily_avg_temp < heating_threshold
    cooling_days = daily_avg_temp > cooling_threshold
    heating_flags = np.repeat(heating_days, 24)
    cooling_flags = np.repeat(cooling_days, 24)
    return daily_avg_temp, heating_days, cooling_days, heating_flags, cooling_flags


# --- Kompatibilitätsfunktionen für system_model_core.py und heatpump_model.py ---

def calculate_heating_load(T_outdoor, irradiance, building_params, usage_df, heating_control=None):
    df = calculate_dynamic_heating_cooling(
        T_outdoor, irradiance, building_params, usage_df, heating_control=heating_control
    )
    return df["Heizlast [kWh/m²]"].to_numpy() * building_params["A_floor"]

def calculate_cooling_load(T_outdoor, irradiance, building_params, usage_df, heating_control=None):
    df = calculate_dynamic_heating_cooling(
        T_outdoor, irradiance, building_params, usage_df, heating_control=heating_control
    )
    return df["Kühllast [kWh/m²]"].to_numpy() * building_params["A_floor"]

def get_heating_day_flags(T_outdoor):
    _, _, _, heating_flags, _ = analyze_heating_cooling_days(T_outdoor)
    return heating_flags.astype(int)

def get_cooling_day_flags(T_outdoor):
    _, _, _, _, cooling_flags = analyze_heating_cooling_days(T_outdoor)
    return cooling_flags.astype(int)

def get_heating_load_on_days(profiles, building_params):
    """
    Get heating load on days.
    
    Args:
        profiles: dict with 'T_outdoor', 'solargains', 'usage_profile' keys
        building_params: dict with building parameters (must include 'A_floor')
    
    Returns:
        numpy array of heating load per hour
    """
    if profiles is None or building_params is None:
        raise ValueError("profiles and building_params must be provided. No legacy fallback available.")
    settings_obj = profiles.get("settings_obj", None)
    heating_control = getattr(settings_obj, "heating_control", None) if settings_obj is not None else None
    df = calculate_dynamic_heating_cooling(
        profiles['T_outdoor'],
        profiles['solargains'],
        building_params,
        profiles['usage_profile'],
        heating_control=heating_control,
    )
    return df["Heizlast [kWh/m²]"].to_numpy() * building_params["A_floor"]

def get_cooling_load_on_days(profiles, building_params):
    """
    Get cooling load on days.
    
    Args:
        profiles: dict with 'T_outdoor', 'solargains', 'usage_profile' keys
        building_params: dict with building parameters (must include 'A_floor')
    
    Returns:
        numpy array of cooling load per hour
    """
    if profiles is None or building_params is None:
        raise ValueError("profiles and building_params must be provided. No legacy fallback available.")
    settings_obj = profiles.get("settings_obj", None)
    heating_control = getattr(settings_obj, "heating_control", None) if settings_obj is not None else None
    df = calculate_dynamic_heating_cooling(
        profiles['T_outdoor'],
        profiles['solargains'],
        building_params,
        profiles['usage_profile'],
        heating_control=heating_control,
    )
    return df["Kühllast [kWh/m²]"].to_numpy() * building_params["A_floor"]


def plot_results(df_hourly, building_params, daily_avg_temp, heating_days, cooling_days, heating_threshold, cooling_threshold):
    # --- Jahresbilanz ---
    print("\n--- Jahres-Energiebilanz ---")
    print(f"QT (Transmission): {df_hourly['QT [W/m²]'].sum() / 1000:.2f} kWh/m²/a")
    print(f"QV (Lüftung):      {df_hourly['QV [W/m²]'].sum() / 1000:.2f} kWh/m²/a")
    print(f"QI (Intern):       {df_hourly['QI [W/m²]'].sum() / 1000:.2f} kWh/m²/a")
    print(f"QS (Solar):        {df_hourly['QS [W/m²]'].sum() / 1000:.2f} kWh/m²/a")
    print(f"Heizlast:          {df_hourly['Heizlast [kWh/m²]'].sum():.2f} kWh/m²/a")
    print(f"Kühllast:          {df_hourly['Kühllast [kWh/m²]'].sum():.2f} kWh/m²/a")

    # --- Plot 1: Temperatur ---
    plt.figure(figsize=(12, 5))
    plt.plot(df_hourly["T_innen [°C]"], label="T_innen", color='black')
    plt.plot(df_hourly["T_außen [°C]"], label="T_außen", color='gray', linestyle=':')
    plt.axhline(y=building_params["T_min"] - 273.15, color='blue', linestyle='--', label="T_min")
    plt.axhline(y=building_params["T_max"] - 273.15, color='red', linestyle='--', label="T_max")
    plt.legend()
    plt.title("Innen- und Außentemperatur über das Jahr")
    plt.grid()
    plt.show()

    # --- Plot 2: Jahres-Energiebilanz ---
    plt.figure(figsize=(8, 5))
    components = ["QT", "QV", "QI", "QS", "Heizlast", "Kühllast"]
    values = [
        df_hourly['QT [W/m²]'].sum() / 1000,
        df_hourly['QV [W/m²]'].sum() / 1000,
        df_hourly['QI [W/m²]'].sum() / 1000,
        df_hourly['QS [W/m²]'].sum() / 1000,
        df_hourly['Heizlast [kWh/m²]'].sum(),
        df_hourly['Kühllast [kWh/m²]'].sum()
    ]
    plt.barh(components, values, color=['orange', 'lightblue', 'green', 'yellow', 'red', 'purple'])
    plt.xlabel("Energie [kWh/m²/a]")
    plt.title("Jahres-Energiebilanz")
    plt.grid(axis='x')
    plt.show()

    # --- Plot 3: Heiz- und Kühltage ---
    plt.figure(figsize=(12, 4))
    plt.plot(daily_avg_temp - 273.15, label="Tagesmittel Außen", color='black')
    plt.axhline(y=heating_threshold - 273.15, color='blue', linestyle='--', label="Heizschwelle")
    plt.axhline(y=cooling_threshold - 273.15, color='red', linestyle='--', label="Kühlschwelle")
    plt.fill_between(range(len(daily_avg_temp)), -20, 50, where=heating_days, color='blue', alpha=0.2, label="Heiztage")
    plt.fill_between(range(len(daily_avg_temp)), -20, 50, where=cooling_days, color='red', alpha=0.2, label="Kühltage")
    plt.legend()
    plt.title("Heiz- und Kühltage basierend auf Tagesmitteltemperaturen")
    plt.grid()
    plt.show()


if __name__ == "__main__":
    location = "Vienna"
    profiles = data.load_profiles(location)
    T_outdoor = profiles['T_outdoor']
    solar_gains = profiles['solargains']
    building_params = data.technologies_global['building']
    usage_df = profiles['usage_profile']

    df_hourly = calculate_dynamic_heating_cooling(T_outdoor, solar_gains, building_params, usage_df)

    heating_threshold = 285.15  # 12°C
    cooling_threshold = 291.45  # 18°C
    daily_avg_temp, heating_days, cooling_days, heating_flags, cooling_flags = analyze_heating_cooling_days(
        T_outdoor, heating_threshold, cooling_threshold
    )

    plot_results(df_hourly, building_params, daily_avg_temp, heating_days, cooling_days, heating_threshold, cooling_threshold)

    # ➡ Gesamtenergiemengen berechnen
    total_heating_energy = df_hourly["Heizlast [kWh/m²]"].sum() * building_params["A_floor"]
    total_cooling_energy = df_hourly["Kühllast [kWh/m²]"].sum() * building_params["A_floor"]

    print("\n--- Gesamte Energiemengen ---")
    print(f"Gesamte Heizenergie: {total_heating_energy:.2f} kWh")
    print(f"Gesamte Kühlenergie: {total_cooling_energy:.2f} kWh")
