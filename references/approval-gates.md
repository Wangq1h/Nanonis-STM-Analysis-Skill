# Approval Gates

Use this reference when an STM/SJTM task contains an agent-chosen scientific decision that should be reviewed by the user before execution.

## When To Gate

Create an approval gate only for these decision types:

- `fit_window`: fitting intervals, superconducting coherence-peak fit ranges, and peak-search windows chosen by the agent.
- `q_selection`: FFT-derived q-vector positions, q windows, and filter sigma values used for QPI, lock-in phase extraction, p_LL, or symmetry analysis.
- `peak_count`: the number of peaks used in multipeak fitting.

Do not create separate approval gates for routine loading, unit conversion, plotting, mean subtraction, window functions, DC masking, file export, or report formatting. Record those choices in provenance instead.

If the user already supplied exact values, record the gate as `user_preapproved` and keep the user-provided values in the report. If the user supplied only a qualitative direction and the agent chooses exact values, create a normal `pending_approval` proposal.

For Bragg or lock-in phase analysis, if the user asks only to "do phase analysis" and gives no q vector, peak, or ROI, ask whether they want to specify the peak/ROI or allow agent search before running peak finding. Human-specified q vectors or ROIs take priority over agent search. Use `scripts/pysidam_agent/bragg_phase.py policy` to enforce this decision point and `inspect-roi` for user-marked peak regions.

## Required Workflow

1. Analyze enough of the data to make a recommendation without executing the gated downstream result.
2. Save `approval_proposal.json` with the proposed parameters, alternatives, evidence paths, and risks.
3. Render a review artifact with `scripts/approval_gate.py render-html` or provide an equivalent static figure and concise explanation.
4. Stop and ask the user to approve, modify, or reject the proposal.
5. Save `approval_decision.json` after the user responds.
6. Validate the decision and continue only with the approved parameters.
7. Link the decision from the final `report.json` under `approval.decision_path`.

The review artifact is advisory. The JSON proposal and JSON decision are the auditable records.

## Proposal Schema

Save this as `approval_proposal.json`:

```json
{
  "schema_version": 1,
  "gate_type": "q_selection",
  "status": "pending_approval",
  "question": "Approve q vectors and filter sigma for lock-in extraction?",
  "agent_recommendation": {
    "q_plus": [0.0, 0.0],
    "q_minus": [0.0, 0.0],
    "sigma": 0.0,
    "units": "cycles/nm"
  },
  "alternatives": [
    {
      "label": "nearby_fft_peak",
      "parameters": {},
      "tradeoff": "May improve FFT amplitude support but changes phase reference."
    }
  ],
  "evidence": {
    "figures": ["figures/fft_q_selection.png"],
    "tables": ["tables/q_candidates.csv"],
    "source_reports": ["report_stage_fft.json"]
  },
  "risks": [
    "Selected q is weakly phase locked along one direction."
  ],
  "approval_options": ["approve", "modify", "reject"]
}
```

Use `gate_type` values only from `fit_window`, `q_selection`, and `peak_count`. Use `status: "user_preapproved"` only when exact values came from the user before execution.

## Decision Schema

Save this as `approval_decision.json`:

```json
{
  "schema_version": 1,
  "proposal_path": "approval_proposal.json",
  "decision": "approved",
  "approved_parameters": {
    "q_plus": [0.0, 0.0],
    "q_minus": [0.0, 0.0],
    "sigma": 0.0
  },
  "user_modifications": {},
  "approval_source": "chat",
  "approved_by": "user",
  "approved_at": "2026-06-23T00:00:00Z"
}
```

Allowed `decision` values are `approved`, `modified`, `rejected`, and `user_preapproved`. For `modified`, put the final executable values in `approved_parameters` and record changes in `user_modifications`.

## CLI

Validate a proposal:

```bash
python3 scripts/approval_gate.py validate-proposal --proposal approval_proposal.json
```

Render a static review page:

```bash
python3 scripts/approval_gate.py render-html --proposal approval_proposal.json --output approval_review.html
```

Validate a decision:

```bash
python3 scripts/approval_gate.py validate-decision --decision approval_decision.json
```

Validate report linkage:

```bash
python3 scripts/approval_gate.py validate-report --report report.json --decision-path approval_decision.json
```

## Evidence Expectations

For `fit_window`, show representative spectra, the proposed interval or peak-search windows, excluded regions, and fit sensitivity if available.

For `q_selection`, show the FFT or relevant q-space map, proposed q points or windows, q-axis units, pixel/q resolution, sigma, and nearby alternatives. For user-provided ROIs, restrict peak refinement to that ROI unless the user approves a broader search.

For `peak_count`, show representative spectra or linecut slices, candidate residual or information-criterion evidence if available, and the peak assignment rule.

Do not turn a weak gate into a strong conclusion. If the evidence is ambiguous, say so in `risks` and in the final report warnings.
