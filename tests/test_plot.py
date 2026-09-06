"""Checks the figure builds for every experiment in both themes.

A chart test cannot say the picture is good. It can say the code runs on every shape of
input it will meet, and that the two rules the eye depends on hold: the smallest
distances get the loudest color, and the binding cells are the ones boxed.
"""

import matplotlib.pyplot as plt
import numpy as np
import pytest
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.colors import to_rgb

from palette_lab import plot


@pytest.fixture(params=[False, True], ids=["light", "dark"])
def theme(request):
    return plot.theme_for(request.param)


def test_figure_builds_for_every_experiment(palette, theme):
    figure = plot.build_figure(palette, theme)
    try:
        assert len(figure.axes) >= 3
        assert figure.get_facecolor() is not None
    finally:
        plt.close(figure)


def test_save_figure_writes_a_png(palette, tmp_path):
    path = plot.save_figure(palette, tmp_path / f"{palette.layout.slug}.png", dpi=60)
    assert path.exists()
    assert path.stat().st_size > 10_000


@pytest.mark.parametrize("dark", [False, True])
def test_small_delta_e_gets_the_loud_color(dark):
    """The whole point of the ramp: low is the problem, so low is the saturated end."""
    theme = plot.theme_for(dark)
    ramp = LinearSegmentedColormap.from_list("delta_e", theme["delta_ramp"])
    low = np.array(ramp(0.0)[:3])
    high = np.array(ramp(1.0)[:3])

    # Saturation, as the spread between the strongest and weakest channel.
    assert low.max() - low.min() > 0.35
    assert high.max() - high.min() < 0.06

    # The harmless end sits near the surface, and the loud end is far from it.
    surface = np.array(to_rgb(theme["surface"]))
    assert np.abs(high - surface).max() < 0.12
    assert np.abs(low - surface).max() > 0.35


@pytest.mark.parametrize("dark", [False, True])
def test_the_ramp_spends_its_red_on_the_bottom_of_the_range(dark):
    """Spread evenly, the whole matrix reads alarming. Half way up must already be calm."""
    ramp = LinearSegmentedColormap.from_list("delta_e", plot.theme_for(dark)["delta_ramp"])
    midpoint = np.array(ramp(0.5)[:3])
    assert midpoint.max() - midpoint.min() < 0.08


def test_emptiest_direction_finds_the_gap():
    # Hues clustered in the first half leave the second half open.
    hues = np.linspace(0.0, 150.0, 6)
    angle = plot.emptiest_direction(hues)
    assert 150.0 < angle < 360.0
    assert min(min(abs(angle - hue), 360.0 - abs(angle - hue)) for hue in hues) > 90.0


def test_emptiest_direction_handles_an_even_spread():
    angle = plot.emptiest_direction(np.linspace(0.0, 360.0, 12, endpoint=False))
    assert 0.0 <= angle < 360.0


def test_binding_pairs_are_what_the_figure_boxes(palette):
    """draw_delta_e boxes palette.binding_pairs, so this pins the set it will draw."""
    matrix = palette.delta_e_matrix
    for row, column in palette.binding_pairs:
        assert matrix[row, column] == pytest.approx(palette.min_delta_e, abs=0.05)
    assert len(palette.binding_pairs) < 66
