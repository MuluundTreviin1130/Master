# Run-of-River Hydro Data

This sublayer contains data inputs that belong to the run-of-river hydro
technology rather than to a generic top-level data bucket.

Current scope:

- Vienna-specific proxy/context files under `Vienna/`
- supporting import path for hydro availability and normalization inputs

Reason for placement:

- these files are technology-specific inputs
- they should live near other technology data instead of as a parallel top-level
  `Data/` branch
