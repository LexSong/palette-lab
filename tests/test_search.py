"""Checks the encoding, the objective and the CMA-ES stage.

The load-bearing claim is that decode always produces a real palette: rings that are
rings, and every color inside sRGB. Nothing downstream re-checks that during the search.
"""

import numpy as np
import pytest

from palette_lab import color
from palette_lab import search
from palette_lab.search import Layout
from tests.conftest import EXPERIMENTS

ALL_LAYOUTS = EXPERIMENTS


def random_params(layout, count=64, seed=7):
    return np.random.default_rng(seed).random((count, layout.n_params))


def test_shared_chroma_is_spelled_in_the_name():
    assert Layout((6, 6), shared_chroma=True).name == "6+6:C"
    assert Layout((6, 6)).name == "6+6"
    assert Layout((6, 6), shared_chroma=True) != Layout((6, 6))


@pytest.mark.parametrize("sizes", [(11,), (6, 7), (0, 12), (-1, 13)])
def test_layout_rejects_sizes_that_are_not_a_palette(sizes):
    with pytest.raises(ValueError):
        Layout(sizes)


@pytest.mark.parametrize("groups", [(0, 1), (0, 1, 2, 3), (0, 2, 2), (1, 1, 1)])
def test_layout_rejects_chroma_groups_that_are_not_slots(groups):
    # One slot per ring, numbered from 0 with no gaps.
    with pytest.raises(ValueError):
        Layout((5, 5, 2), chroma_groups=groups)


def test_layout_rejects_chroma_groups_that_contradict_shared_chroma():
    with pytest.raises(ValueError):
        Layout((5, 5, 2), shared_chroma=True, chroma_groups=(0, 1, 1))


def test_chroma_groups_are_stored_however_they_were_spelled():
    """A layout that spells its slots out equals one that leaves them implied."""
    assert Layout((6, 6)).groups == (0, 1)
    assert Layout((6, 6), shared_chroma=True).groups == (0, 0)
    assert Layout((6, 6)) == Layout((6, 6), chroma_groups=(0, 1))
    assert len({Layout((6, 6)), Layout((6, 6), chroma_groups=(0, 1))}) == 1


@pytest.mark.parametrize("floor", [-0.01, 0.99, 1.5])
def test_layout_rejects_a_lightness_floor_outside_the_range(floor):
    with pytest.raises(ValueError):
        Layout((6, 6), lightness_floor=floor)


def test_a_lightness_floor_raises_the_bottom_of_the_decoded_range():
    floor = 0.45
    layout = Layout((6, 6), lightness_floor=floor)
    assert layout.lightness_range == (floor, search.LIGHTNESS_RANGE[1])
    oklch, lightness, _ = search.decode(random_params(layout, 64, seed=3), layout)
    assert lightness.min() >= floor
    assert oklch[:, :, 0].min() >= floor


@pytest.mark.parametrize("layout", ALL_LAYOUTS, ids=lambda layout: layout.name)
def test_parameter_count_matches_the_free_variables(layout):
    # A lightness and a phase per ring, a rho per chroma slot, and one gap logit per color
    # past a ring's first.
    expected = 2 * layout.n_rings + layout.n_chroma + sum(size - 1 for size in layout.sizes)
    assert layout.n_params == expected


def test_parameter_counts_are_what_we_think_they_are():
    assert Layout((6, 6)).n_params == 16
    assert Layout((5, 7)).n_params == 16
    # Sharing one chroma removes exactly one variable.
    assert Layout((6, 6), shared_chroma=True).n_params == 15
    # Three rings, and two of them share a chroma, so two chroma variables not three.
    assert Layout((5, 5, 2), chroma_groups=(0, 1, 1)).n_params == 17
    assert Layout((5, 5, 2)).n_params == 18
    # A floor bounds a variable rather than adding one.
    assert Layout((5, 5, 2), chroma_groups=(0, 1, 1), lightness_floor=0.45).n_params == 17


@pytest.mark.parametrize("layout", ALL_LAYOUTS, ids=lambda layout: layout.name)
def test_decode_always_lands_inside_srgb(layout):
    oklch, _, _ = search.decode(random_params(layout, 200), layout)
    excess = color.gamut_excess(color.oklab_to_linear_srgb(color.oklch_to_oklab(oklch)))
    assert excess.max() == 0.0


@pytest.mark.parametrize("layout", ALL_LAYOUTS, ids=lambda layout: layout.name)
def test_decoded_rings_are_rings(layout):
    oklch, lightness, chroma = search.decode(random_params(layout), layout)
    assert oklch.shape == (64, search.N_COLORS, 3)
    for ring in range(layout.n_rings):
        members = layout.ring_of_color == ring
        assert np.ptp(oklch[:, members, 0], axis=1).max() < 1e-12
        assert np.ptp(oklch[:, members, 1], axis=1).max() < 1e-12
        assert np.abs(oklch[:, members, 0] - lightness[:, ring, None]).max() < 1e-12
        assert np.abs(oklch[:, members, 1] - chroma[:, ring, None]).max() < 1e-12


@pytest.mark.parametrize("layout", ALL_LAYOUTS, ids=lambda layout: layout.name)
def test_hues_are_distinct_and_span_one_turn(layout):
    """Gaps come from a softmax scaled to 360, so a ring covers the circle exactly once."""
    params = random_params(layout, 32)
    oklch, _, _ = search.decode(params, layout)
    for ring, size in enumerate(layout.sizes):
        members = layout.ring_of_color == ring
        hues = oklch[:, members, 2]
        assert hues.shape[1] == size
        for row in hues:
            wrapped = np.sort(row % 360.0)
            gaps = np.diff(np.append(wrapped, wrapped[0] + 360.0))
            assert np.min(gaps) > 0.0
            assert np.sum(gaps) == pytest.approx(360.0, abs=1e-9)


@pytest.mark.parametrize("layout", ALL_LAYOUTS, ids=lambda layout: layout.name)
def test_rho_of_one_puts_each_chroma_slot_on_the_gamut_boundary(layout):
    """rho=1 means the worst hue a chroma slot has to cover sits exactly at its limit."""
    params = random_params(layout, 16)
    params[:, layout.n_rings : layout.n_rings + layout.n_chroma] = 1.0
    oklch, _, _ = search.decode(params, layout)
    chroma_of_color = layout.chroma_of_color
    for slot in range(layout.n_chroma):
        members = chroma_of_color == slot
        ceiling = color.max_chroma(oklch[:, members, 0], oklch[:, members, 2]).min(axis=1)
        assert np.abs(ceiling - oklch[:, members, 1][:, 0]).max() < 1e-9


@pytest.mark.parametrize("sizes", [(6, 6), (5, 7)])
def test_shared_chroma_gives_every_color_the_same_chroma(sizes):
    layout = Layout(sizes, shared_chroma=True)
    oklch, _, chroma = search.decode(random_params(layout, 64), layout)
    assert np.ptp(oklch[:, :, 1], axis=1).max() < 1e-12
    assert np.ptp(chroma, axis=1).max() < 1e-12


@pytest.mark.parametrize("sizes", [(6, 6), (5, 7)])
def test_shared_chroma_is_capped_by_the_worst_hue_in_the_whole_palette(sizes):
    """One shared chroma cannot exceed what the most constrained ring could reach alone."""
    layout = Layout(sizes, shared_chroma=True)
    params = random_params(layout, 32)
    params[:, layout.n_rings : layout.n_rings + layout.n_chroma] = 1.0
    oklch, _, _ = search.decode(params, layout)

    ceiling = color.max_chroma(oklch[:, :, 0], oklch[:, :, 2])
    assert np.abs(ceiling.min(axis=1) - oklch[:, 0, 1]).max() < 1e-9
    per_ring = np.stack([ceiling[:, layout.ring_of_color == r].min(axis=1) for r in range(layout.n_rings)], axis=1)
    assert np.all(oklch[:, 0, 1] <= per_ring.min(axis=1) + 1e-12)


def test_decode_is_deterministic():
    layout = Layout((6, 6))
    params = random_params(layout, 8)
    first, _, _ = search.decode(params, layout)
    second, _, _ = search.decode(params, layout)
    assert np.array_equal(first, second)


def test_score_is_the_minimum_plus_a_sliver_of_the_mean():
    layout = Layout((5, 7))
    params = random_params(layout, 20)
    oklch, _, _ = search.decode(params, layout)
    minimum, mean = search.delta_e_stats(oklch)
    assert search.score(params, layout) == pytest.approx(minimum + search.TIEBREAK_WEIGHT * mean)
    # The tiebreak must never reorder two palettes whose minima differ meaningfully.
    assert search.TIEBREAK_WEIGHT * mean.max() < 0.5


@pytest.mark.parametrize("layout", ALL_LAYOUTS, ids=lambda layout: layout.name)
def test_equal_spacing_baseline_really_is_equally_spaced(layout):
    value, params = search.equal_spacing_baseline(layout, n_lightness=13)
    oklch, _, _ = search.decode(params[None, :], layout)
    for ring, size in enumerate(layout.sizes):
        hues = np.sort(oklch[0, layout.ring_of_color == ring, 2] % 360.0)
        gaps = np.diff(np.append(hues, hues[0] + 360.0))
        assert np.ptp(gaps) < 1e-9
        assert gaps[0] == pytest.approx(360.0 / size)
    assert search.delta_e_stats(oklch)[0][0] == pytest.approx(value)


@pytest.mark.parametrize("layout", ALL_LAYOUTS, ids=lambda layout: layout.name)
def test_search_beats_equal_spacing(layout):
    candidates, baseline = search.search_layout(layout, restarts=2, max_evaluations=2500, seed=3)
    oklch, _, _ = search.decode(candidates[0][None, :], layout)
    assert float(search.delta_e_stats(oklch)[0][0]) > baseline


def test_search_returns_candidates_sorted_best_first():
    layout = Layout((6, 6))
    candidates, _ = search.search_layout(layout, restarts=2, max_evaluations=400, seed=1)
    values = search.score(np.array(candidates), layout)
    assert np.all(np.diff(values) <= 1e-12)


def test_search_is_reproducible_from_its_seed():
    layout = Layout((6, 6))
    first, _ = search.search_layout(layout, restarts=2, max_evaluations=400, seed=11)
    second, _ = search.search_layout(layout, restarts=2, max_evaluations=400, seed=11)
    assert np.array_equal(first[0], second[0])


def test_softmax_rows_sum_to_one():
    logits = np.random.default_rng(0).normal(size=(10, 7)) * 5.0
    weights = search._softmax(logits)
    assert weights.sum(axis=1) == pytest.approx(np.ones(10))
    assert weights.min() > 0.0


@pytest.mark.parametrize("ceiling", [-0.01, 0.0, 0.99, 1.5])
def test_layout_rejects_a_lightness_ceiling_outside_the_range(ceiling):
    with pytest.raises(ValueError):
        Layout((6, 6), lightness_ceiling=ceiling)


def test_layout_rejects_a_ceiling_at_or_below_its_floor():
    with pytest.raises(ValueError):
        Layout((6, 6), lightness_floor=0.60, lightness_ceiling=0.60)
    with pytest.raises(ValueError):
        Layout((6, 6), lightness_floor=0.70, lightness_ceiling=0.60)


def test_a_lightness_ceiling_lowers_the_top_of_the_decoded_range():
    floor, ceiling = 0.60, 0.85
    layout = Layout((6, 6), lightness_floor=floor, lightness_ceiling=ceiling)
    assert layout.lightness_range == (floor, ceiling)
    oklch, lightness, _ = search.decode(random_params(layout, 64, seed=5), layout)
    assert lightness.min() >= floor
    assert lightness.max() <= ceiling
    assert oklch[:, :, 0].max() <= ceiling


def test_a_label_replaces_the_name_built_from_ring_sizes():
    """Twelve rings would otherwise be called "1+1+...+1", which is no use as a filename."""
    layout = Layout((1,) * 12, chroma_groups=(0,) * 12, label="bright12")
    assert layout.name == "bright12"
    assert layout.slug == "bright12"
    assert Layout((6, 6)).name == "6+6", "a layout without a label keeps the sizes"


def test_the_baseline_grid_coarsens_so_many_rings_still_fit():
    """The enumeration is more than exponential in ring count, so the grid has to give."""
    assert search.baseline_resolution(2) == search.BASELINE_LIGHTNESS_STEPS
    assert search.baseline_resolution(3) == search.BASELINE_LIGHTNESS_STEPS, "shipped layouts keep the fine grid"
    for rings in (2, 3, 4, 6, 12):
        steps = search.baseline_resolution(rings)
        assert steps >= 2
        assert search.baseline_grid_size(rings, steps) <= search.BASELINE_MAX_CANDIDATES


def test_the_baseline_stays_inside_a_layouts_lightness_band():
    layout = Layout((1,) * 12, chroma_groups=(0,) * 12, lightness_floor=0.60, lightness_ceiling=0.85)
    _, params = search.equal_spacing_baseline(layout)
    oklch, _, _ = search.decode(params[None, :], layout)
    assert oklch[:, :, 0].min() >= 0.60 - 1e-9
    assert oklch[:, :, 0].max() <= 0.85 + 1e-9
