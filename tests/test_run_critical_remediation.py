from __future__ import annotations

import csv
from pathlib import Path
import shutil
import zipfile

from scripts import run_critical_remediation as remediation


NON_ASCII_TRACKED_FILES = (
    "pages/7_因子選股.py",
    "thesis/chapter5_實證結果.md",
)


def _git_quote_path(rel_path: str) -> bytes:
    pieces: list[str] = []
    for byte in rel_path.encode("utf-8"):
        if byte >= 0x80 or byte < 0x20:
            pieces.append(f"\\{byte:03o}")
        elif byte == ord('"'):
            pieces.append('\\"')
        elif byte == ord("\\"):
            pieces.append("\\\\")
        else:
            pieces.append(chr(byte))
    return f'"{"".join(pieces)}"'.encode("ascii")


def test_source_provenance_includes_quoted_non_ascii_tracked_paths(monkeypatch):
    missing = [
        rel for rel in NON_ASCII_TRACKED_FILES
        if not (remediation.ROOT / rel).is_file()
    ]
    assert missing == []

    quoted_tracked_stdout = b"".join(
        _git_quote_path(rel) + b"\n" for rel in NON_ASCII_TRACKED_FILES
    )

    def fake_run_git_bytes(args: list[str]) -> tuple[int, bytes, bytes]:
        if args == ["ls-files"]:
            return 0, quoted_tracked_stdout, b""
        if args == ["ls-files", "--others", "--exclude-standard"]:
            return 0, b"", b""
        if args == remediation._working_tree_patch_args():
            return 0, b"", b""
        raise AssertionError(f"Unexpected git args: {args}")

    def rel_for_test(path: Path) -> str:
        resolved = Path(path).resolve()
        try:
            return resolved.relative_to(remediation.ROOT.resolve()).as_posix()
        except ValueError:
            return resolved.as_posix()

    test_dir = remediation.ROOT / "results" / "remediation" / "_pytest_source_provenance"
    shutil.rmtree(test_dir, ignore_errors=True)

    try:
        monkeypatch.setattr(remediation, "_run_git_bytes", fake_run_git_bytes)
        monkeypatch.setattr(remediation, "_rel", rel_for_test)
        monkeypatch.setattr(remediation, "SOURCE_PROVENANCE_DIR", test_dir)

        provenance = remediation._write_source_provenance([])

        hashes_path = test_dir / "source_file_hashes.csv"
        with hashes_path.open("r", newline="", encoding="utf-8") as handle:
            hash_list_paths = {row["path"] for row in csv.DictReader(handle)}

        snapshot_path = test_dir / "source_snapshot.zip"
        with zipfile.ZipFile(snapshot_path) as archive:
            snapshot_paths = set(archive.namelist())

        for rel in NON_ASCII_TRACKED_FILES:
            assert rel in hash_list_paths
            assert rel in snapshot_paths
        assert provenance["source_file_count"] == len(NON_ASCII_TRACKED_FILES)
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_source_provenance_patch_excludes_generated_results_before_writes(monkeypatch):
    tracked_source = "modules/cross_sectional_ic.py"
    assert (remediation.ROOT / tracked_source).is_file()

    source_patch = (
        b"diff --git a/modules/cross_sectional_ic.py b/modules/cross_sectional_ic.py\n"
        b"--- a/modules/cross_sectional_ic.py\n"
        b"+++ b/modules/cross_sectional_ic.py\n"
    )
    test_dir = remediation.ROOT / "results" / "remediation" / "_pytest_source_patch_exclusion"
    shutil.rmtree(test_dir, ignore_errors=True)
    diff_calls: list[list[str]] = []

    def fake_run_git_bytes(args: list[str]) -> tuple[int, bytes, bytes]:
        if args == ["ls-files"]:
            return 0, f"{tracked_source}\n".encode("utf-8"), b""
        if args == ["ls-files", "--others", "--exclude-standard"]:
            return 0, b"", b""
        if args and args[0] == "diff":
            diff_calls.append(args)
            assert args == remediation._working_tree_patch_args()
            assert ":(exclude)results/**" in args
            assert not (test_dir / "source_file_hashes.csv").exists()
            assert not (test_dir / "source_snapshot.zip").exists()
            return 0, source_patch, b""
        raise AssertionError(f"Unexpected git args: {args}")

    def rel_for_test(path: Path) -> str:
        resolved = Path(path).resolve()
        try:
            return resolved.relative_to(remediation.ROOT.resolve()).as_posix()
        except ValueError:
            return resolved.as_posix()

    try:
        monkeypatch.setattr(remediation, "_run_git_bytes", fake_run_git_bytes)
        monkeypatch.setattr(remediation, "_rel", rel_for_test)
        monkeypatch.setattr(remediation, "SOURCE_PROVENANCE_DIR", test_dir)

        provenance = remediation._write_source_provenance([])

        patch_bytes = (test_dir / "working_tree_patch.diff").read_bytes()
        assert diff_calls == [remediation._working_tree_patch_args()]
        assert patch_bytes == source_patch
        assert b"results/remediation" not in patch_bytes
        assert b"source_file_hashes.csv" not in patch_bytes
        assert b"source_snapshot.zip" not in patch_bytes
        assert provenance["exclusions"][
            "generated_results_and_cache_paths_excluded_from_working_tree_patch"
        ] is True
        assert "results/**" in provenance["exclusions"]["working_tree_patch_excluded_patterns"]
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_manifest_output_hashes_ignore_stale_leftover_files():
    test_dir = remediation.OUT_DIR / "_pytest_manifest_hash_scope"
    shutil.rmtree(test_dir, ignore_errors=True)
    try:
        test_dir.mkdir(parents=True)
        current_path = test_dir / "current_run_artifact.txt"
        stale_path = test_dir / "clean_env_install_status.json"
        current_path.write_text("generated by this test run\n", encoding="utf-8")
        stale_path.write_text('{"status": "stale"}\n', encoding="utf-8")

        output_hashes = remediation._build_current_run_output_hashes([current_path])

        assert remediation._rel(current_path) in output_hashes
        assert remediation._rel(stale_path) not in output_hashes
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)
