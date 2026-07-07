# STM/SJTM Data Processing v0.2.3

## Approval Gate Workflow

- Adds a standardized approval gate contract for `fit_window`, `q_selection`, and `peak_count` decisions.
- Adds `approval_proposal.json` and `approval_decision.json` validation through `scripts/approval_gate.py`.
- Documents when agents must stop for user approval before formal fitting, lock-in, p_LL, QPI, or multipeak batch execution.

## Verification

- Run `python3 scripts/validate_package.py`.
- Run `python3 -m unittest tests.test_approval_gate -v`.
