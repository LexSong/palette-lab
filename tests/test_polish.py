"""Checks the SLSQP refinement.

The contract is narrow: polish returns a palette that is a valid ringed palette, inside
sRGB, and never worse than what it was given.
"""

import numpy as np
import pytest

from palette_lab import color
from palette_lab import polish as polish_module
from palette_lab import search
from palette_lab.polish import polish
from palette_lab.search import Layout
from tests.conftest import EXPERIMENTS

ALL_LAYOUTS = EXPERIMENTS


def a_starting_point(layout, seed=5):
    candidates, _ = search.search_layout(layout, restarts=1, max_evaluations=400, seed=seed)
    return candidates[0]


def minimum_delta_e(oklch):
    return float(color.pairwise_delta_e(color.oklab_to_lab(color.oklch_to_oklab(oklch))).min())


@pytest.mark.parametrize("layout", ALL_LAYOUTS, ids=lambda layout: layout.name)
def test_pack_and_unpack_round_trip(layout):
    rng = np.random.default_rng(0)
    lightness = rng.uniform(0.2, 0.9, layout.n_rings)
    chroma = rng.uniform(0.02, 0.2, layout.n_rings)
    hues = rng.uniform(0, 360, search.N_COLORS)

    # Rings sharing a chroma slot must start out equal, because pack keeps one value
    # per slot and unpack spreads it back over every ring in that slot.
    for slot in range(layout.n_chroma):
        members = [ring for ring in range(layout.n_rings) if layout.groups[ring] == slot]
        chroma[members] = chroma[members[0]]

    variables = polish_module.pack(lightness, chroma, hues, 23.5, layout)
    assert len(variables) == 1 + layout.n_rings + layout.n_chroma + search.N_COLORS

    recovered_t, oklch = polish_module.unpack(variables[None, :], layout)
    assert recovered_t[0] == pytest.approx(23.5)
    assert oklch[0, :, 0] == pytest.approx(lightness[layout.ring_of_color])
    assert oklch[0, :, 1] == pytest.approx(chroma[layout.ring_of_color])
    assert oklch[0, :, 2] == pytest.approx(hues)


@pytest.mark.parametrize("layout", ALL_LAYOUTS, ids=lambda layout: layout.name)
def test_polish_never_makes_a_palette_worse(layout):
    params = a_starting_point(layout)
    before = minimum_delta_e(search.decode(params[None, :], layout)[0][0])
    _, after = polish(params, layout)
    assert after >= before - 1e-12


@pytest.mark.parametrize("layout", ALL_LAYOUTS, ids=lambda layout: layout.name)
def test_polished_palette_is_a_valid_ringed_palette(layout):
    oklch, reported = polish(a_starting_point(layout), layout)

    assert oklch.shape == (search.N_COLORS, 3)
    assert color.gamut_excess(color.oklab_to_linear_srgb(color.oklch_to_oklab(oklch))).max() == 0.0
    assert minimum_delta_e(oklch) == pytest.approx(reported, abs=1e-9)

    for ring in range(layout.n_rings):
        members = layout.ring_of_color == ring
        assert np.ptp(oklch[members, 0]) < 1e-9
        assert np.ptp(oklch[members, 1]) < 1e-9
        assert np.all(np.diff(oklch[members, 2]) > 0.0)

    chroma_of_color = layout.chroma_of_color
    for slot in range(layout.n_chroma):
        assert np.ptp(oklch[chroma_of_color == slot, 1]) < 1e-9

    assert oklch[:, 0].min() >= layout.lightness_range[0] - 1e-9


def test_clamp_pulls_an_out_of_gamut_ring_back_in():
    # One shared slot covers all 12, so the whole palette clamps to a single chroma.
    layout = Layout((6, 6), shared_chroma=True)
    hues = np.linspace(0, 360, 12, endpoint=False)
    # 0.35 is outside sRGB at every hue for this lightness.
    oklch = np.stack([np.full(12, 0.7), np.full(12, 0.35), hues], axis=-1)
    assert color.gamut_excess(color.oklab_to_linear_srgb(color.oklch_to_oklab(oklch))).max() > 0.0

    clamped = polish_module.clamp_into_gamut(oklch, layout)
    assert color.gamut_excess(color.oklab_to_linear_srgb(color.oklch_to_oklab(clamped))).max() == 0.0
    assert np.ptp(clamped[:, 1]) == 0.0
    assert np.array_equal(clamped[:, 2], hues)


def test_clamp_leaves_an_in_gamut_ring_alone():
    layout = Layout((6, 6), shared_chroma=True)
    hues = np.linspace(0, 360, 12, endpoint=False)
    oklch = np.stack([np.full(12, 0.7), np.full(12, 0.02), hues], axis=-1)
    assert np.array_equal(polish_module.clamp_into_gamut(oklch, layout), oklch)


def test_sorting_hues_keeps_the_same_colors():
    layout = Layout((5, 7))
    rng = np.random.default_rng(2)
    oklch = np.stack(
        [
            np.array([0.4] * 5 + [0.8] * 7),
            np.array([0.1] * 5 + [0.12] * 7),
            rng.uniform(0, 360, 12),
        ],
        axis=-1,
    )
    sorted_oklch = polish_module.sort_hues_within_rings(oklch, layout)
    assert sorted(np.round(sorted_oklch[:, 2], 9)) == sorted(np.round(oklch[:, 2], 9))
    for ring in range(layout.n_rings):
        members = layout.ring_of_color == ring
        assert np.all(np.diff(sorted_oklch[members, 2]) > 0)
        assert np.array_equal(sorted_oklch[members, 0], oklch[members, 0])


def test_jacobian_matches_a_plain_finite_difference():
    def function(batch):
        return np.stack([batch[:, 0] ** 2, batch[:, 1] * batch[:, 2], np.sin(batch[:, 0])], axis=1)

    point = np.array([0.3, -0.7, 1.1])
    ours = polish_module._jacobian(function, point)
    expected = np.array([[2 * 0.3, 0.0, 0.0], [0.0, 1.1, -0.7], [np.cos(0.3), 0.0, 0.0]])
    assert np.abs(ours - expected).max() < 1e-6


def test_polish_keeps_a_palette_inside_the_layouts_lightness_band():
    """Refinement runs after the search, so nothing else would catch an escape upward."""
    layout = Layout((1,) * 12, chroma_groups=(0,) * 12, lightness_floor=0.60, lightness_ceiling=0.85)
    rng = np.random.default_rng(11)
    for _ in range(4):
        oklch, _ = polish(rng.uniform(0.05, 0.95, layout.n_params), layout)
        assert oklch[:, 0].min() >= 0.60 - 1e-9
        assert oklch[:, 0].max() <= 0.85 + 1e-9
