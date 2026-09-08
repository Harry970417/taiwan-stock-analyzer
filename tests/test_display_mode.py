# tests/test_display_mode.py
# Confirms BACKTEST_DISPLAY_MODE=showcase|research separation, and -- the
# critical safety property -- that showcase mode can never resolve to the
# gitignored exports/ working directory, under any env var input including
# unset, empty, misspelled, or garbage values.
# Run: python -m pytest tests/test_display_mode.py -v

from pathlib import Path

import pytest

from modules.display_mode import (
    RESEARCH,
    RESEARCH_PATHS,
    SHOWCASE,
    SHOWCASE_PATHS,
    get_data_root,
    get_dataset_path,
    get_display_mode,
)

FAKE_ROOT = Path("C:/fake_project_root")


def test_default_mode_is_showcase(monkeypatch):
    monkeypatch.delenv("BACKTEST_DISPLAY_MODE", raising=False)
    assert get_display_mode() == SHOWCASE


@pytest.mark.parametrize("raw", ["showcase", "SHOWCASE", "  showcase  ", "", "bogus", "prod", "exports"])
def test_non_research_values_resolve_to_showcase(monkeypatch, raw):
    monkeypatch.setenv("BACKTEST_DISPLAY_MODE", raw)
    assert get_display_mode() == SHOWCASE


@pytest.mark.parametrize("raw", ["research", "RESEARCH", "  research  ", "Research"])
def test_research_values_resolve_to_research(monkeypatch, raw):
    monkeypatch.setenv("BACKTEST_DISPLAY_MODE", raw)
    assert get_display_mode() == RESEARCH


@pytest.mark.parametrize("mode_input", [SHOWCASE, "", "bogus", None, "exports", "research_typo"])
def test_showcase_data_root_never_contains_exports(monkeypatch, mode_input):
    """The critical guarantee: no input to get_data_root, however garbled,
    can make the showcase path pass through exports/. mode_input=None means
    'read from the environment', which is set to a non-research value for
    this test so the expected resolution is unambiguously showcase."""
    monkeypatch.delenv("BACKTEST_DISPLAY_MODE", raising=False)
    root = get_data_root(FAKE_ROOT, mode_input)
    parts = str(root).replace("\\", "/").split("/")
    assert "exports" not in parts
    assert "assets" in parts
    assert "backtest_release" in parts


def test_research_mode_data_root_is_exports():
    root = get_data_root(FAKE_ROOT, RESEARCH)
    parts = str(root).replace("\\", "/").split("/")
    assert "exports" in parts
    assert "tw_us_backtest" in parts


def test_showcase_and_research_path_maps_have_the_same_keys():
    # A dataset available in one mode must be available in the other --
    # otherwise switching modes silently breaks a section of the page.
    assert set(SHOWCASE_PATHS.keys()) == set(RESEARCH_PATHS.keys())


@pytest.mark.parametrize("key", list(SHOWCASE_PATHS.keys()))
def test_get_dataset_path_resolves_for_every_known_key_in_both_modes(key):
    showcase_path = get_dataset_path(FAKE_ROOT, key, SHOWCASE)
    research_path = get_dataset_path(FAKE_ROOT, key, RESEARCH)
    assert "exports" not in str(showcase_path).replace("\\", "/").split("/")
    assert "exports" in str(research_path).replace("\\", "/").split("/")


def test_get_dataset_path_rejects_unknown_key():
    with pytest.raises(KeyError):
        get_dataset_path(FAKE_ROOT, "not_a_real_dataset", SHOWCASE)


def test_showcase_mode_is_never_selected_by_a_research_looking_but_wrong_value(monkeypatch):
    # Guards against a future typo like "reserach" or "Research " (trailing
    # garbage) silently being treated as research when it should fail safe.
    for wrong in ["reserach", "research ", " research", "researchmode", "re search"]:
        monkeypatch.setenv("BACKTEST_DISPLAY_MODE", wrong)
        mode = get_display_mode()
        if wrong.strip().lower() == RESEARCH:
            assert mode == RESEARCH
        else:
            assert mode == SHOWCASE
