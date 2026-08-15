# Eval report — SUT: `labgraph-baseline`

- Total: **5**
- Passed: **2**
- Failed: **3**
- Pass rate: **40%**

## Per-question results

| ID | Status | Distinct sources | Reasons |
|----|--------|------------------|---------|
| lift-atlas-001 | FAIL | 2 | expected sources not retrieved: 2024-03-team-sync.md |
| lift-beacon-001 | PASS | 2 | - |
| lift-cedar-001 | PASS | 2 | - |
| lift-delta-001 | FAIL | 2 | expected sources not retrieved: 2024-05-team-sync.md |
| lift-echo-001 | FAIL | 2 | expected sources not retrieved: 2024-06-team-sync.md |

## Failing questions in detail

### lift-atlas-001

> Who investigated gradually introducing difficult examples, and what happened next?

- Missing sources: 2024-03-team-sync.md
- Matched sources: training_stability_2024.md

### lift-delta-001

> What followed the unreliable ablation finding?

- Missing sources: 2024-05-team-sync.md
- Matched sources: method_y_ablation.md

### lift-echo-001

> What followed the convergence and early-stability experiment?

- Missing sources: 2024-06-team-sync.md
- Matched sources: method_z_experiments.md
