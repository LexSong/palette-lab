"""Checks the color pipeline against colour-science and against coloraide.

The formulas here are colour-science's. What can break is our wiring: a transposed
matrix, a re-anchored whitepoint that drifts, degrees passed where radians belong.
coloraide is an independent implementation, so agreement between the two catches wiring
errors that a self-consistent round trip would miss.
"""

import colour
import numpy as np
import pytest
from coloraide import Color

from palette_lab import color


@pytest.fixture
def oklab_samples():
    """A spread of Oklab values, most in gamut and some deliberately outside it."""
    rng = np.random.default_rng(20260906)
    lightness = rng.uniform(0.05, 0.98, 400)
    chroma = rng.uniform(0.0, 0.35, 400)
    hue = rng.uniform(0.0, 360.0, 400)
    return color.oklch_to_oklab(np.stack([lightness, chroma, hue], axis=-1))


def test_white_and_black_land_where_they_should():
    """Re-anchoring the Oklab matrix onto sRGB's white is the whole point of it."""
    white = color.oklab_to_linear_srgb(np.array([1.0, 0.0, 0.0]))
    assert white == pytest.approx([1.0, 1.0, 1.0], abs=1e-12)
    black = color.oklab_to_linear_srgb(np.array([0.0, 0.0, 0.0]))
    assert black == pytest.approx([0.0, 0.0, 0.0], abs=1e-12)

    assert color.oklab_to_lab(np.array([1.0, 0.0, 0.0])) == pytest.approx([100.0, 0.0, 0.0], abs=1e-9)
    assert color.to_hex(white) == "#ffffff"
    assert color.to_hex(black) == "#000000"


def test_folded_path_computes_what_colour_science_computes(oklab_samples):
    """Loose on purpose.

    A wiring error moves a color by a lot, so this catches one. It cannot be tight,
    because colour's rounded matrices are the 1.6e-3 error we re-anchored away from.
    `test_linear_srgb_matches_coloraide` is the tight check.
    """
    reference = colour.XYZ_to_sRGB(colour.models.Oklab_to_XYZ(oklab_samples), apply_cctf_encoding=False)
    assert np.abs(color.oklab_to_linear_srgb(oklab_samples) - reference).max() < 2e-3


def test_xyz_round_trip(oklab_samples):
    xyz = color.oklab_to_xyz(oklab_samples)
    linear = color.oklab_to_linear_srgb(oklab_samples)
    assert np.abs(xyz @ color.MATRIX_XYZ_TO_RGB.T - linear).max() < 1e-12
    assert color.linear_srgb_to_xyz(np.ones(3)) == pytest.approx(color.WHITEPOINT_XYZ, abs=1e-15)


def test_srgb_matrix_agrees_with_the_one_colour_ships():
    """We rebuild it for precision, so it must still be the sRGB matrix, not another one."""
    assert np.abs(color.MATRIX_XYZ_TO_RGB - colour.models.RGB_COLOURSPACE_sRGB.matrix_XYZ_to_RGB).max() < 1e-3


def test_linear_srgb_round_trips_to_oklab(oklab_samples):
    linear = color.oklab_to_linear_srgb(oklab_samples)
    assert np.abs(color.linear_srgb_to_oklab(linear) - oklab_samples).max() < 1e-9


def test_oklch_round_trip(oklab_samples):
    oklch = color.oklab_to_oklch(oklab_samples)
    assert np.abs(color.oklch_to_oklab(oklch) - oklab_samples).max() < 1e-12
    assert oklch[..., 2].min() >= 0.0
    assert oklch[..., 2].max() < 360.0


def test_linear_srgb_matches_coloraide(oklab_samples):
    ours = color.oklab_to_linear_srgb(oklab_samples)
    theirs = np.array([Color("oklab", list(v)).convert("srgb-linear")[:3] for v in oklab_samples])
    assert np.abs(ours - theirs).max() < 1e-6


def test_cie_lab_matches_coloraide(oklab_samples):
    ours = color.oklab_to_lab(oklab_samples)
    theirs = np.array([Color("oklab", list(v)).convert("lab-d65")[:3] for v in oklab_samples])
    assert np.abs(ours - theirs).max() < 1e-3


def test_delta_e_2000_matches_coloraide(oklab_samples):
    sample = oklab_samples[:60]
    ours = color.delta_e_matrix(color.oklab_to_lab(sample))
    colors = [Color("oklab", list(v)) for v in sample]
    for i in range(0, 60, 7):
        for j in range(i + 1, 60, 11):
            assert ours[i, j] == pytest.approx(colors[i].delta_e(colors[j], method="2000"), abs=1e-3)


def test_delta_e_matrix_is_symmetric_with_zero_diagonal(oklab_samples):
    matrix = color.delta_e_matrix(color.oklab_to_lab(oklab_samples[:20]))
    assert np.abs(matrix - matrix.T).max() == 0.0
    assert np.abs(np.diagonal(matrix)).max() == 0.0


def test_pairwise_delta_e_broadcasts_over_leading_axes(oklab_samples):
    batch = color.oklab_to_lab(oklab_samples[:96].reshape(8, 12, 3))
    pairs = color.pairwise_delta_e(batch)
    assert pairs.shape == (8, 66)
    rows, cols = color.triu_indices(12)
    for k in range(8):
        assert np.abs(pairs[k] - color.delta_e_matrix(batch[k])[rows, cols]).max() < 1e-9


@pytest.mark.parametrize("lightness", [0.15, 0.4, 0.62, 0.85, 0.95])
def test_max_chroma_sits_on_the_gamut_boundary(lightness):
    hues = np.linspace(0.0, 360.0, 73)
    chroma = color.max_chroma(np.full_like(hues, lightness), hues)
    assert chroma.min() > 0.0

    def excess(scale):
        oklch = np.stack([np.full_like(hues, lightness), chroma * scale, hues], axis=-1)
        return color.gamut_excess(color.oklab_to_linear_srgb(color.oklch_to_oklab(oklch)))

    # Just inside is in gamut, just outside is not. That is what "boundary" means.
    assert excess(1.0).max() == 0.0
    assert (excess(1.0 + 1e-4) > 0.0).all()


def test_max_chroma_matches_coloraide_gamut_fit():
    hues = np.linspace(0.0, 360.0, 25, endpoint=False)
    lightness = 0.72
    ours = color.max_chroma(np.full_like(hues, lightness), hues)
    for hue, chroma in zip(hues, ours, strict=True):
        assert Color("oklch", [lightness, chroma, hue]).in_gamut("srgb", tolerance=1e-5)
        assert not Color("oklch", [lightness, chroma * 1.01, hue]).in_gamut("srgb", tolerance=1e-5)


def test_hex_round_trip(oklab_samples):
    linear = color.oklab_to_linear_srgb(oklab_samples)
    linear = linear[color.gamut_excess(linear) == 0.0]
    recovered = color.from_hex(color.to_hex(linear))
    # 8-bit quantization is the only loss, so half a step in the encoded domain.
    encoded_error = np.abs(color.linear_srgb_to_srgb(recovered) - color.linear_srgb_to_srgb(linear)).max()
    assert encoded_error <= 0.5 / 255.0 + 1e-9


def test_hex_matches_coloraide(oklab_samples):
    linear = color.oklab_to_linear_srgb(oklab_samples)
    keep = color.gamut_excess(linear) == 0.0
    ours = color.to_hex(linear[keep])
    theirs = [Color("oklab", list(v)).convert("srgb").to_string(hex=True) for v in oklab_samples[keep]]
    assert ours == theirs


def test_gamut_excess_reports_the_worst_channel():
    assert color.gamut_excess(np.array([0.5, 0.5, 0.5])) == 0.0
    assert color.gamut_excess(np.array([0.0, 1.0, 0.5])) == 0.0
    assert color.gamut_excess(np.array([-0.2, 0.5, 1.3])) == pytest.approx(0.3)
    assert color.gamut_excess(np.array([[-0.2, 0.5, 0.5], [0.1, 0.2, 0.3]])).tolist() == pytest.approx([0.2, 0.0])
