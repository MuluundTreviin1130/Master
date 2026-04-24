# Coding Rules

These rules apply to ongoing repo work.

## Core

- No silent fallbacks.
- No unnecessary hardcodes.
- `Settings/` and `Data/` are SSOT.
- Fail fast on missing required inputs.
- Keep the code extensible for future larger MES scope.
- Treat simplicity, clarity, logic, overview, and extensibility as central criteria for every code extension.
- Before writing or changing code, consult `AGENTS.md` and this file.

## Simplicity and explanation

- Prefer the simplest structure and control flow that still satisfy the modeling need.
- Do not hide intent in clever or compressed code when a clearer variant is available.
- For new non-trivial logic, document the code densely: comments should make nearly line by line clear why it exists, why it is written that way, and what it means.
- Simplify first, then explain; comments must not be used to justify avoidable structural complexity.

## Activation

- New behavior must be activated explicitly via settings or typed data.
- Do not hide new defaults in runtime code.
- Do not silently switch variants or downgrade to legacy logic.

## Data and reporting

- Document work steps in `Documentation/worklog.md`.
- Put open tasks in `Documentation/Planning/TODO.md`.
- Put literature and data provenance in `Documentation/Sources/`.
- Keep exported KPIs/source tags explicit when behavior depends on calibration or settings.
- Every new long-lived folder or sublayer must contain a meaningful `README.md`.
- If an existing folder materially changes its purpose, update its `README.md`.
- When larger repo changes accumulate, create a clean commit and push the work to GitHub regularly.

## Modeling

- Prefer additive integration over replacing working structures without need.
- Avoid repo-wide refactors unless required by the task.
- Use calibrated or literature-backed values only where they are actually supported.
- Do not present partially calibrated fields as fully calibrated.

## Error handling

- Missing required inputs should raise explicit errors.
- Zero is only acceptable when the corresponding feature or technology is explicitly disabled.
- Legacy compatibility is allowed only when explicit and documented.
