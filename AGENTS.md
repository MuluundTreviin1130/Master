# Agent Rules

This repo uses the following working rules as operational SSOT for coding work.

Core rules:
- No silent fallbacks.
- No unnecessary hardcoding.
- Settings and Data are the single source of truth.
- Prefer fail-fast validation over implicit recovery.
- Preserve extensibility for future MES scope (`DH`, `bus`, `EC`, further sectors).
- Simplicity, clarity, logic, overview, and extensibility are central criteria for every code extension.

Task-start rule:
- Before writing or changing code, consult this file and `Documentation/coding_rules.md`.

Documentation rules:
- Log relevant work in `Documentation/worklog.md`.
- Track open follow-ups in `Documentation/Planning/TODO.md`.
- Store source notes in `Documentation/Sources/`.
- Keep documentation concise but sufficient to reconstruct the main steps.
- When creating a new long-lived folder or sublayer, add or update a meaningful `README.md`.
- When larger repo changes accumulate, create a clean commit and push the work to GitHub regularly.

Implementation rules:
- Do not hide missing inputs behind default zeros unless the feature is explicitly disabled by settings.
- Do not introduce behavior-changing defaults outside `Settings/` or data SSOT files.
- When adding new logic, make activation explicit through settings or typed data.
- Prefer additive extensions over destructive restructuring.
- Prefer the simplest structure and control flow that still meet the modeling need.
- New non-trivial code should be documented densely: comments should make nearly line by line clear why code exists, why it is written that way, and what it means.

See also:
- `Documentation/coding_rules.md`
