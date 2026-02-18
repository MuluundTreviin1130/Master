# effects/

This directory is the canonical storage location for *exported* environmental effect factors
(the JSON files consumed by the optimizer).

Recommended layout:
- effects/brightway/static/<country>/{Grid,PV,BESS}.json
- effects/premise/<country>/<iam>/<scenario>/<year>/{Grid,PV,BESS}.json

Each dataset folder may include a `manifest.json` with provenance metadata.
