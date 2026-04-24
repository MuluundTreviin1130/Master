# Data Package

Data loading and parameter assembly for optimization.

## LCA layout

Static LCA JSON files are expected under:

- `Data/LCA_data/static/<country_code>/PV.json`
- `Data/LCA_data/static/<country_code>/BESS.json`
- `Data/LCA_data/static/<country_code>/Grid.json`

For hydrogen-enabled runs (`enable_h2=True`), additionally required:

- `Data/LCA_data/static/<country_code>/ELY.json`
- `Data/LCA_data/static/<country_code>/H2_TANK.json`
- `Data/LCA_data/static/<country_code>/FC.json`

Each file must provide at least:

- `infra.<impact_key>`
- `op.<impact_key>`

## Notes

- `Data/assembly/params.py` assembles merged runtime parameters.
- `Data/profiles/` contains profile assets plus the canonical registry/loader layer.
- `Data/quality/` contains data-quality diagnostics and their explicit outputs.
