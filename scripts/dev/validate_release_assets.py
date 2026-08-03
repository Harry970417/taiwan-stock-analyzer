"""
Independent release-gate validator for assets/backtest_release/v1/.

Thin CLI wrapper around modules/release_validation.py, which is the single
source of truth for these checks -- pages/15_台美股策略回測.py imports the
same module at runtime so the CLI gate and the page's own guard can never
drift apart.

Runs completely separately from scripts/dev/build_release_assets.py (which
builds the package) -- this script only reads and checks. A passing build
script does not guarantee an untampered or internally-consistent package;
this is the second, independent set of eyes before anything is pushed or
deployed.

Exit code 0 = all checks passed. Exit code 1 = at least one check failed.

Run: python scripts/dev/validate_release_assets.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from modules.release_validation import run_all_checks

RELEASE = ROOT / "assets" / "backtest_release" / "v1"

results = run_all_checks(RELEASE)

print(f"Release asset validation: {RELEASE.relative_to(ROOT)}\n")
n_pass = 0
for r in results:
    tag = "PASS" if r["passed"] else "FAIL"
    if r["passed"]:
        n_pass += 1
    print(f"  [{tag}] {r['name']}\n         {r['detail']}")

n_total = len(results)
print(f"\n{n_pass}/{n_total} checks passed.")

if n_total == 0 or n_pass < n_total:
    print("\nRELEASE VALIDATION FAILED. Do not push or deploy this release.")
    sys.exit(1)

print("\nRelease validation PASSED.")
sys.exit(0)
