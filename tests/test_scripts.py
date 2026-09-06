"""Checks the three experiment scripts and the visualizer.

`scripts/` is not a package, so the path juggling below is how these get imported. Each
experiment script exposes `LAYOUT`, which is what lets these tests drive the real script
without spawning a subprocess.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

from palette_lab import experiment
from palette_lab import palette as palette_module
from tests.conftest import EXPERIMENTS

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
EXPERIMENT_SCRIPTS = sorted(path.stem for path in SCRIPTS.glob("experiment_*.py"))


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


visualize = load_script("visualize_palette")


def test_there_are_exactly_three_experiment_scripts():
    assert EXPERIMENT_SCRIPTS == [
        "experiment_5plus7",
        "experiment_6plus6",
        "experiment_6plus6_shared_chroma",
    ]


def test_the_scripts_declare_the_layouts_the_tests_assume():
    """conftest.EXPERIMENTS restates the list. This is what stops the two drifting."""
    declared = {load_script(name).LAYOUT for name in EXPERIMENT_SCRIPTS}
    assert declared == set(EXPERIMENTS)


@pytest.mark.parametrize("name", EXPERIMENT_SCRIPTS)
def test_each_script_has_a_docstring_saying_why_it_exists(name):
    module = load_script(name)
    assert module.__doc__ is not None
    assert len(module.__doc__.strip().splitlines()) > 1, "one line is a label, not a reason"


@pytest.mark.parametrize("name", EXPERIMENT_SCRIPTS)
def test_running_a_script_writes_one_json_named_for_its_layout(name, tmp_path):
    layout = load_script(name).LAYOUT
    argv = ["--restarts", "1", "--evals", "300", "--polish-top", "1", "--out-dir", str(tmp_path), "--quiet"]
    assert experiment.main(layout, argv) == 0

    written = list(tmp_path.glob("*.json"))
    assert [path.name for path in written] == [f"{layout.slug}.json"]

    palette = palette_module.load(written[0])
    assert palette.layout == layout
    assert palette.gamut_excess() == 0.0
    assert len(palette.hexes) == 12
    assert written[0].stat().st_size < 4000


def test_visualizer_renders_a_saved_palette(palette, tmp_path):
    json_path = tmp_path / f"{palette.layout.slug}.json"
    palette_module.save(palette, json_path)

    assert visualize.main([str(json_path), "--no-show", "--dpi", "60"]) == 0
    assert (tmp_path / f"{palette.layout.slug}.png").exists()

    assert visualize.main([str(json_path), "--no-show", "--dark", "--dpi", "60"]) == 0
    assert (tmp_path / f"{palette.layout.slug}-dark.png").exists()


def test_visualizer_honours_an_explicit_save_path(palette, tmp_path):
    json_path = tmp_path / "in.json"
    palette_module.save(palette, json_path)
    output = tmp_path / "elsewhere" / "wheel.png"

    assert visualize.main([str(json_path), "--no-show", "--save", str(output), "--dpi", "60"]) == 0
    assert output.exists()
