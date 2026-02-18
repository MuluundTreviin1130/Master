def allocate_share(cfg: dict, category: str) -> float:
    method = cfg["method"]
    if method == "grandfathering":
        return float(cfg["grandfathering"]["share_by_category"][category])
    if method == "per_capita":
        world = float(cfg["world_population"])
        reg = float(cfg["region_population"])
        alpha = float(cfg["alpha_energy_by_category"].get(category, 0.0))
        return (reg/world)*alpha if world > 0 else 0.0
    if method == "fixed":
        # share ist schon SoSOS, handled elsewhere
        return 1.0
    raise ValueError(method)
