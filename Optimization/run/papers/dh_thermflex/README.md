# Vienna DH Thermflex Paper Runners

This folder bundles paper-specific runners for the Vienna district-heating
Thermflex study.

Typical contents:

- case runners
- analysis runners
- surrogate recheck runners
- selected-candidate replay runners
- dedicated gap-debug runners for `day_ahead -> two_stage`

Reason for placement:

- these scripts are not generic optimization entry points
- they belong to one study family and should not clutter `Optimization/run/`
