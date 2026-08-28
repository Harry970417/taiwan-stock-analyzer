# Reproducibility Manifest

Last updated: 2026-08-02

The authoritative machine-readable manifest for the corrected V1 replay is:

```text
results/remediation/manifest.json
```

## Formal Environment

| Item | Value |
|------|-------|
| Main project Python | 3.11 |
| Main dependency declaration | `requirements.txt` / `pyproject.toml` with `pandas<3`, `numpy<2` |
| Remediation replay lock | `requirements.lock.txt` records the Python 3.14.5 direct dependency set used for the 2026-08-02 replay |
| Formal command | `python scripts/run_critical_remediation.py` |
| Random seed | 42 |
| Cache policy | Verify pinned SHA-256 before reading `results/data/universe_data.pkl` and `results/data/factor_panels.pkl`; stop if absent or mismatched |

The main application runtime remains the documented Python 3.11 baseline used by
Docker and CI. The Python 3.14.5 dependency set is retained only as the
remediation replay lock because `results/remediation/manifest.json` records that
environment for the prior formal replay.

## Reproduction Steps

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.lock.txt
.\.venv\Scripts\python -m pytest tests -q
.\.venv\Scripts\python scripts\run_critical_remediation.py
```

For the main Python 3.11 application/CI baseline, install `requirements.txt`.
For the 2026-08-02 remediation replay environment specifically, use:

```powershell
.\.venv\Scripts\python -m pip install -r requirements.lock.txt
.\.venv\Scripts\python scripts\run_critical_remediation.py
```

## Clean-Environment Verification Status

Status: not re-attempted for the current source in remediation round 3.

The runner records the existing status file as historical, not as current
verification. A previous clean-env attempt failed at dependency installation:

```powershell
.\.venv\Scripts\python -m pip install -r requirements.lock.txt
```

The observed failure was:

```text
ERROR: Could not find a version that satisfies the requirement pandas==3.0.3
ERROR: No matching distribution found for pandas==3.0.3
```

Before claiming clean-environment reproducibility for the current source, rerun
the clean install and formal command in the intended environment. No
system-site-packages fallback should be used, because that would rely on
undeclared global packages and would not satisfy clean-environment
reproducibility.

## Result Provenance

Old outputs in `results/` are preserved in place. Their provenance status is
recorded in:

```text
results/remediation/provenance.json
```

The formal run is not reproducible from `git_commit` alone when the worktree is
dirty. The runner records the exact source snapshot, working-tree patch, and
untracked source file hashes used for the run in:

```text
results/remediation/source_provenance/
```

The pickle cache inputs are documented in `results/data/CACHE_INPUTS.md`. The
runner verifies their expected hashes before `pickle.load`; a cache mismatch is
a hard failure.

New corrected selected-universe outputs are under:

```text
results/remediation/selected_universe_corrected/
```

The bias-controlled result layer is blocked and documented at:

```text
results/remediation/bias_controlled/bias_controlled_status.json
```

## Universe Limitation

The V1 study uses a hardcoded 16-stock selected survivor list. It is not a
complete point-in-time Taiwan equity universe. The repository does not contain
complete historical delisted, merged, renamed, or suspended companies with
point-in-time liquidity eligibility.

Therefore survivorship bias is not eliminated. Corrected conclusions apply only
to the existing selected universe and must not be generalized to the full Taiwan
stock market.
