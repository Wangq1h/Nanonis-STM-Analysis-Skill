# v0.2.1

This release tightens superconducting gap-fitting workflow safety.

Highlights:

- Adds a required mode gate for ambiguous superconducting or two-band gap fitting prompts.
- Uses the explicit `Ask before fitting` rule name in release validation.
- Defines `strict-pysidam-compatible` mode for parameter comparability with the default PySIDAM-backed bridge.
- Defines `gap-priority experimental` mode for recorded nuisance terms, fit-window selection, and gap-region weighting.
- Requires agents to ask before fitting when the requested mode is unclear, and to ask again for later ambiguous requests.
- Updates package validation so this rule remains present in the skill entry point, gap-fit quick card, and fitting recipe.

Release checklist:

- Run `python3 scripts/validate_package.py`.
- Sync the installed skill with `python3 scripts/sync_installed_skill.py`.
- Verify the installed copy with its own `scripts/validate_package.py`.
