# Pedigree And Data Quality Records

This folder stores pedigree-based data quality records for LCA datasets used by
the model.

Scope:
- Dataset-level quality metadata for technologies referenced by the LCA layer
- Country-specific records, aligned with `Data/LCA_data/static/<country>/`
- Pedigree dimensions following the 5-factor approach used in the manuscript:
  - reliability
  - completeness
  - technological representativeness
  - geographical representativeness
  - temporal representativeness

Current intent:
- Keep the raw assessment data close to the LCA data layer
- Keep uncertainty, sensitivity, and SR-vs-DQR analysis outside this folder
- Avoid hidden defaults: every technology should have an explicit pedigree record
- Cover all technologies with an existing LCA role in the model, not only newly
  added technologies

Recommended workflow:
1. Create or update one JSON file per technology and country.
2. Fill dataset references from `static/<country>/*.json` and, where available,
   `mappings/activity_map.json`.
3. Score the five pedigree dimensions on a 1-5 scale.
4. Compute the DQR from the five scores using the weakest-score weighting rule.
5. Use the records later in top-level analysis workflows for:
   - DQR summary tables
   - SR-vs-DQR criticality plots
   - uncertainty prioritisation

Pedigree score convention:
- `1` = best / highest quality
- `5` = worst / lowest quality

DQR formula used here:
- `DQR = (sum(scores) + weakest_score * 4) / 9`

This matches the five-dimension weighting logic used in the manuscript and the
supporting slides, where the weakest quality indicator receives additional
weight.

Interpretation used in the manuscript:
- `DQR < 1.6` : high quality
- `1.6 <= DQR <= 3.0` : medium quality
- `DQR > 3.0` : data estimate / low quality

Notes:
- Records may be created before scoring is complete.
- In that case, set `assessment_status` to `pending_scoring` and leave the
  pedigree scores as `null`.
- The loader and DQR utilities should raise if a complete DQR is requested for
  an incomplete record.
- Technologies such as `V2H` and `ThermFlex` are not listed as standalone
  pedigree records at this stage because they are currently represented through
  operational logic rather than dedicated LCA dataset files in
  `Data/LCA_data/static/<country>/`.
