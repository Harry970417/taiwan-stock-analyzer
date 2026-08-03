# tests/test_release_validation.py
# modules/release_validation.py is the single source of truth used by both
# scripts/dev/validate_release_assets.py (CLI gate) and the dashboard page's
# runtime guard -- it needs its own direct test coverage, not just an
# indirect check via the page.
# Run: python -m pytest tests/test_release_validation.py -v

import json
import shutil
from pathlib import Path

import pytest

from modules.release_validation import is_release_valid

ROOT = Path(__file__).resolve().parent.parent
RELEASE = ROOT / "assets" / "backtest_release" / "v1"


def test_current_release_package_is_valid():
    valid, results = is_release_valid(RELEASE)
    failed = [r for r in results if not r["passed"]]
    assert valid, f"release package failed validation: {failed}"
    assert len(results) >= 15


def test_missing_manifest_fails_cleanly(tmp_path):
    empty_dir = tmp_path / "empty_release"
    empty_dir.mkdir()
    valid, results = is_release_valid(empty_dir)
    assert valid is False
    assert results and results[0]["name"].startswith("manifest.json exists")


def test_tampered_checksum_is_detected(tmp_path):
    copy_dir = tmp_path / "tampered_release"
    shutil.copytree(RELEASE, copy_dir)
    with open(copy_dir / "core_metrics.csv", "a", encoding="utf-8") as f:
        f.write("\ntampered,row\n")

    valid, results = is_release_valid(copy_dir)
    assert valid is False
    checksum_check = next(r for r in results if "checksum" in r["name"].lower())
    assert checksum_check["passed"] is False


def test_tampered_manifest_seed_count_is_detected(tmp_path):
    copy_dir = tmp_path / "bad_seed_count_release"
    shutil.copytree(RELEASE, copy_dir)
    manifest_path = copy_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["random_seed_count"] = 42
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    valid, results = is_release_valid(copy_dir)
    assert valid is False
    seed_check = next(r for r in results if "random_seed_count" in r["name"])
    assert seed_check["passed"] is False


def test_extra_untracked_file_is_detected(tmp_path):
    copy_dir = tmp_path / "extra_file_release"
    shutil.copytree(RELEASE, copy_dir)
    (copy_dir / "sneaky_extra_file.csv").write_text("a,b\n1,2\n", encoding="utf-8")

    valid, results = is_release_valid(copy_dir)
    assert valid is False
    unexpected_check = next(r for r in results if "unexpected files" in r["name"])
    assert unexpected_check["passed"] is False


def test_forbidden_phrase_is_detected_but_negated_form_is_not(tmp_path):
    copy_dir = tmp_path / "phrase_release"
    shutil.copytree(RELEASE, copy_dir)
    (copy_dir / "reports" / "final_report.md").write_text(
        "本策略已驗證高報酬，值得投入。", encoding="utf-8"
    )
    valid, results = is_release_valid(copy_dir)
    assert valid is False
    phrase_check = next(r for r in results if "forbidden" in r["name"] or "prohibited" in r["name"])
    assert phrase_check["passed"] is False


def test_negated_claim_does_not_false_positive(tmp_path):
    copy_dir = tmp_path / "negated_release"
    shutil.copytree(RELEASE, copy_dir)
    (copy_dir / "reports" / "final_report.md").write_text(
        "本策略未優於被動基準，CAGR 超額報酬未獲驗證。", encoding="utf-8"
    )
    valid, results = is_release_valid(copy_dir)
    phrase_check = next(r for r in results if "forbidden" in r["name"] or "prohibited" in r["name"])
    assert phrase_check["passed"] is True, phrase_check["detail"]
