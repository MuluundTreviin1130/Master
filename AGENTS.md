# Agent Rules

This repo uses the following working rules as operational SSOT for coding work.

Core rules:
- No silent fallbacks.
- No unnecessary hardcoding.
- Settings and Data are the single source of truth.
- Prefer fail-fast validation over implicit recovery.
- Preserve extensibility for future MES scope (`DH`, `bus`, `EC`, further sectors).
- Simplicity, clarity, logic, overview, and extensibility are central criteria for every code extension.
- Work token- and context-efficiently: inspect only what is needed, avoid noisy outputs, keep edits scoped, and prefer concise implementation/documentation paths.

Task-start rule:
- Before writing or changing code, consult this file and `Documentation/coding_rules.md`.

Documentation rules:
- Log relevant work in `Documentation/worklog.md`.
- Track open follow-ups in `Documentation/Planning/TODO.md`.
- Store source notes in `Documentation/Sources/`.
- Keep documentation concise but sufficient to reconstruct the main steps.
- Do not update `worklog` and `TODO` after every micro-step. Prefer periodic, coarse-grained documentation once a meaningful block of work, decision, or result has accumulated.
- When creating a new long-lived folder or sublayer, add or update a meaningful `README.md`.
- Reusable run artifacts for learning should not be scattered ad hoc across new side paths; keep raw run outputs in their source run folders and register reusable truth/model/diagnostic artifacts through the `Learning/datasets/` inventory and curated dataset paths.
- When larger repo changes accumulate, create a clean commit and push the work to GitHub regularly.

Implementation rules:
- Do not hide missing inputs behind default zeros unless the feature is explicitly disabled by settings.
- Do not introduce behavior-changing defaults outside `Settings/` or data SSOT files.
- When adding new logic, make activation explicit through settings or typed data.
- Prefer additive extensions over destructive restructuring.
- Prefer the simplest structure and control flow that still meet the modeling need.
- New non-trivial code should be documented densely: comments should make nearly line by line clear why code exists, why it is written that way, and what it means.
- Keep agent work environmentally and context conscious: avoid unnecessary file reads, broad rewrites, duplicated analysis, and oversized responses when a smaller precise step is enough.

See also:
- `Documentation/coding_rules.md`
