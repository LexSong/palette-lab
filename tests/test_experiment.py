"""Checks the shared pipeline, and `verify` in particular.

`verify` is the last gate before a palette reaches disk. Each case below is a way the
search could go wrong that nothing downstream would notice.
"""

import numpy as np
import pytest

from palette_lab import experiment
from palette_lab.search import Layout


def a_ring(lightness=0.7, chroma=0.02, offset=0.0):
    hues = np.linspace(0, 360, 12, endpoint=False) + offset
    return np.stack([np.full(12, lightness), np.full(12, chroma), hues], axis=-1)


def test_verify_accepts_a_good_palette(palette):
    minimum = experiment.verify(palette.oklch, palette.layout, baseline=0.0)
    assert minimum == pytest.approx(palette.min_delta_e, abs=1e-9)


def test_verify_rejects_an_out_of_gamut_palette():
    oklch = a_ring(chroma=0.4)
    with pytest.raises(AssertionError, match="out of sRGB"):
        experiment.verify(oklch, Layout((6, 6)), baseline=0.0)


def test_verify_rejects_a_ring_whose_lightness_drifts():
    oklch = a_ring()
    oklch[3, 0] = 0.71
    with pytest.raises(AssertionError, match="not a ring"):
        experiment.verify(oklch, Layout((6, 6)), baseline=0.0)


def test_verify_rejects_a_ring_whose_chroma_drifts():
    oklch = a_ring()
    oklch[9, 1] = 0.03
    with pytest.raises(AssertionError, match="chroma varies"):
        experiment.verify(oklch, Layout((6, 6)), baseline=0.0)


def test_verify_rejects_two_chromas_when_the_layout_says_one():
    """Each ring is internally uniform here, so only the shared-chroma check can catch it."""
    layout = Layout((6, 6), shared_chroma=True)
    oklch = a_ring()
    oklch[6:, 1] = 0.03
    with pytest.raises(AssertionError, match="meant to share it"):
        experiment.verify(oklch, layout, baseline=0.0)
    # The same palette is fine when the rings are allowed their own chroma.
    experiment.verify(oklch, Layout((6, 6)), baseline=0.0)


def test_verify_rejects_two_chromas_inside_one_group():
    """Rings 1 and 2 share a slot, so they may not disagree even though ring 0 may."""
    layout = Layout((5, 5, 2), chroma_groups=(0, 1, 1))
    oklch = a_ring()
    oklch[:5, 1] = 0.04
    with pytest.raises(AssertionError, match="slot 1"):
        oklch[10:, 1] = 0.03
        experiment.verify(oklch, layout, baseline=0.0)
    # Ring 0 carrying its own chroma is the point of the grouping, so that stays legal.
    oklch[10:, 1] = 0.02
    experiment.verify(oklch, layout, baseline=0.0)


def test_verify_rejects_a_palette_under_the_layout_floor():
    layout = Layout((6, 6), lightness_floor=0.45)
    oklch = a_ring(lightness=0.44)
    with pytest.raises(AssertionError, match="floor"):
        experiment.verify(oklch, layout, baseline=0.0)
    # The same palette passes once the floor allows it.
    experiment.verify(oklch, Layout((6, 6)), baseline=0.0)


def test_verify_rejects_a_result_that_lost_to_the_baseline():
    with pytest.raises(AssertionError, match="baseline"):
        experiment.verify(a_ring(), Layout((6, 6)), baseline=99.0)


def test_run_produces_a_saveable_palette(experiment_layout):
    palette = experiment.run(experiment_layout, restarts=1, evals=400, polish_top=1, seed=2)

    assert palette.layout == experiment_layout
    assert palette.oklch.shape == (12, 3)
    assert palette.gamut_excess() == 0.0
    assert palette.config["gamut"] == "sRGB"
    assert palette.config["seed"] == 2
    # The baseline and the wall clock describe the search, not the palette, so they stay out.
    assert "equal_spacing_baseline" not in palette.config
    assert "seconds" not in palette.config


def test_main_writes_the_json_and_only_plots_when_asked(experiment_layout, tmp_path):
    argv = ["--restarts", "1", "--evals", "300", "--polish-top", "1", "--out-dir", str(tmp_path), "--quiet"]
    assert experiment.main(experiment_layout, argv) == 0

    json_path = tmp_path / f"{experiment_layout.slug}.json"
    assert json_path.exists()
    assert not (tmp_path / f"{experiment_layout.slug}.png").exists()

    assert experiment.main(experiment_layout, [*argv, "--plot"]) == 0
    assert (tmp_path / f"{experiment_layout.slug}.png").exists()
