# Formal Remediation Cache Inputs

`scripts/run_critical_remediation.py` requires these local cache inputs:

| Path | SHA-256 |
|------|---------|
| `results/data/universe_data.pkl` | `ea49d59e4293caa6f77602fe16428cdf704795f18b625d348192909e43a7ee92` |
| `results/data/factor_panels.pkl` | `0d641852f25fcac8ce9aedc94a47446a24aebeff4dd479e5a75a59ff9f9ecfee` |

The runner verifies each hash before `pickle.load`. These two files are the
fixed inputs for the formal selected-universe remediation replay; the runner
does not regenerate them from live APIs because that would introduce data drift.

If these files are not distributed through Git, restore the exact same snapshot
to the paths above before running:

```powershell
python scripts/run_critical_remediation.py
```
