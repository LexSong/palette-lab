"""OKLCh, sRGB and CIEDE2000, vectorized over any leading axes.

`colour-science` supplies every formula and constant. This module re-derives two things
from those constants rather than calling the library entry points.

Speed. The gamut bisection runs ~32 conversions per CMA-ES generation, and
`colour.XYZ_to_sRGB` costs ~0.26 ms per call. Folding the chain into two 3x3 matrices
drops that to ~0.002 ms. `tests/test_color.py` checks the folded path against the
library it came from.

Precision. colour stores the sRGB primaries matrix rounded, and Oklab's LMS matrix is
anchored to a D65 that differs from sRGB's by 0.0002 in Z. Composed, those two put sRGB
white at Oklab L=1.0003 and move the gamut boundary by ~0.1%, which is enough to change
a hex digit. We rebuild the primaries matrix with `colour.normalised_primary_matrix` and
re-anchor Oklab's LMS matrix onto the white that matrix actually produces. sRGB white
then maps to Oklab (1, 0, 0) and to CIE Lab (100, 0, 0) exactly, and the whole pipeline
agrees with coloraide to 4e-7. coloraide does the same re-derivation for the same reason.

Two lightness scales meet here, so names always say which. Oklab `L` runs 0-1. CIE Lab
`L` runs 0-100, and CIEDE2000 is defined on that one.
"""

import colour
import numpy as np
from colour.models import RGB_COLOURSPACE_sRGB
from colour.models.oklab import MATRIX_1_XYZ_TO_LMS
from colour.models.oklab import MATRIX_2_LAB_TO_LMS

MATRIX_RGB_TO_XYZ = colour.normalised_primary_matrix(RGB_COLOURSPACE_sRGB.primaries, RGB_COLOURSPACE_sRGB.whitepoint)
MATRIX_XYZ_TO_RGB = np.linalg.inv(MATRIX_RGB_TO_XYZ)

WHITEPOINT_XYZ = MATRIX_RGB_TO_XYZ @ np.ones(3)

# CIE Lab needs its whitepoint as chromaticity coordinates. Y is already 1 here, so
# XYZ -> xy -> XYZ returns WHITEPOINT_XYZ unchanged and white lands on (100, 0, 0).
ILLUMINANT_XY = colour.XYZ_to_xy(WHITEPOINT_XYZ)

# Oklab -> LMS'. Column 0 is 1 by construction, but colour stores it rounded to
# 1.00000005, which alone would leave white 3e-7 off. Restore the exact value.
MATRIX_OKLAB_TO_LMS_P = MATRIX_2_LAB_TO_LMS.copy()
MATRIX_OKLAB_TO_LMS_P[:, 0] = 1.0

# LMS -> linear sRGB, with the XYZ step folded in. Each row of the XYZ -> LMS matrix is
# scaled so that WHITEPOINT_XYZ maps to LMS (1, 1, 1); that is the re-anchoring.
_MATRIX_XYZ_TO_LMS = MATRIX_1_XYZ_TO_LMS / (MATRIX_1_XYZ_TO_LMS @ WHITEPOINT_XYZ)[:, None]
MATRIX_LMS_TO_RGB = MATRIX_XYZ_TO_RGB @ np.linalg.inv(_MATRIX_XYZ_TO_LMS)

# Chroma large enough to sit outside sRGB at every lightness, so bisection always
# brackets the boundary. The most saturated sRGB color reaches about C=0.32.
CHROMA_CEILING = 0.45


def oklch_to_oklab(oklch):
    """(..., 3) of (L, C, h in degrees) -> (..., 3) of (L, a, b)."""
    oklch = np.asarray(oklch, dtype=float)
    hue = np.radians(oklch[..., 2])
    chroma = oklch[..., 1]
    return np.stack([oklch[..., 0], chroma * np.cos(hue), chroma * np.sin(hue)], axis=-1)


def oklab_to_oklch(oklab):
    """(..., 3) of (L, a, b) -> (..., 3) of (L, C, h in degrees), h in [0, 360)."""
    oklab = np.asarray(oklab, dtype=float)
    a = oklab[..., 1]
    b = oklab[..., 2]
    return np.stack([oklab[..., 0], np.hypot(a, b), np.degrees(np.arctan2(b, a)) % 360.0], axis=-1)


def oklab_to_linear_srgb(oklab):
    """(..., 3) Oklab -> (..., 3) linear sRGB. Any channel outside [0, 1] is out of gamut."""
    lms_p = np.asarray(oklab, dtype=float) @ MATRIX_OKLAB_TO_LMS_P.T
    return (lms_p**3) @ MATRIX_LMS_TO_RGB.T


def linear_srgb_to_oklab(linear_rgb):
    """(..., 3) linear sRGB -> (..., 3) Oklab."""
    lms = np.asarray(linear_rgb, dtype=float) @ np.linalg.inv(MATRIX_LMS_TO_RGB).T
    return np.cbrt(lms) @ np.linalg.inv(MATRIX_OKLAB_TO_LMS_P).T


def linear_srgb_to_xyz(linear_rgb):
    """(..., 3) linear sRGB -> (..., 3) XYZ under D65."""
    return np.asarray(linear_rgb, dtype=float) @ MATRIX_RGB_TO_XYZ.T


def oklab_to_xyz(oklab):
    """(..., 3) Oklab -> (..., 3) XYZ under D65."""
    return linear_srgb_to_xyz(oklab_to_linear_srgb(oklab))


def linear_srgb_to_lab(linear_rgb):
    """(..., 3) linear sRGB -> (..., 3) CIE Lab, the input CIEDE2000 expects."""
    return colour.XYZ_to_Lab(linear_srgb_to_xyz(linear_rgb), illuminant=ILLUMINANT_XY)


def oklab_to_lab(oklab):
    """(..., 3) Oklab -> (..., 3) CIE Lab."""
    return linear_srgb_to_lab(oklab_to_linear_srgb(oklab))


def linear_srgb_to_srgb(linear_rgb):
    """Apply the sRGB transfer function. (..., 3) linear -> (..., 3) display-encoded."""
    return colour.cctf_encoding(np.asarray(linear_rgb, dtype=float), function="sRGB")


def srgb_to_linear_srgb(srgb):
    """Undo the sRGB transfer function."""
    return colour.cctf_decoding(np.asarray(srgb, dtype=float), function="sRGB")


def gamut_excess(linear_rgb):
    """(..., 3) linear sRGB -> (...) how far the worst channel falls outside [0, 1].

    Zero means in gamut.
    """
    linear_rgb = np.asarray(linear_rgb, dtype=float)
    return np.maximum(np.maximum(-linear_rgb, linear_rgb - 1.0).max(axis=-1), 0.0)


def max_chroma(lightness, hue_deg, steps=32):
    """Largest in-gamut Oklab chroma at each (lightness, hue). Broadcasts.

    Bisection on C. At C=0 the color is a neutral gray, in gamut for any lightness in
    [0, 1], so the low end of the bracket is always feasible.
    """
    lightness, hue_deg = np.broadcast_arrays(np.asarray(lightness, float), np.asarray(hue_deg, float))
    hue = np.radians(hue_deg)
    cos_h, sin_h = np.cos(hue), np.sin(hue)

    low = np.zeros_like(lightness)
    high = np.full_like(lightness, CHROMA_CEILING)
    for _ in range(steps):
        mid = 0.5 * (low + high)
        oklab = np.stack([lightness, mid * cos_h, mid * sin_h], axis=-1)
        inside = gamut_excess(oklab_to_linear_srgb(oklab)) <= 0.0
        low = np.where(inside, mid, low)
        high = np.where(inside, high, mid)
    return low


def triu_indices(n):
    """Row and column indices of the strict upper triangle of an n x n matrix."""
    return np.triu_indices(n, k=1)


def pairwise_delta_e(lab, indices=None):
    """(..., n, 3) CIE Lab -> (..., n*(n-1)/2) CIEDE2000 over the upper triangle.

    Pass `indices` from `triu_indices` to skip rebuilding it inside a loop.
    """
    lab = np.asarray(lab, dtype=float)
    if indices is None:
        indices = triu_indices(lab.shape[-2])
    rows, cols = indices
    return colour.difference.delta_E_CIE2000(lab[..., rows, :], lab[..., cols, :])


def delta_e_matrix(lab):
    """(n, 3) CIE Lab -> (n, n) symmetric CIEDE2000 matrix with a zero diagonal."""
    lab = np.asarray(lab, dtype=float)
    size = lab.shape[0]
    matrix = np.zeros((size, size))
    rows, cols = triu_indices(size)
    matrix[rows, cols] = pairwise_delta_e(lab, (rows, cols))
    return matrix + matrix.T


def to_hex(linear_rgb):
    """(..., 3) linear sRGB -> hex strings. Clips, so check the gamut first."""
    encoded = np.clip(linear_srgb_to_srgb(linear_rgb), 0.0, 1.0)
    channels = np.rint(encoded * 255.0).astype(int)
    hexes = ["#{:02x}{:02x}{:02x}".format(*value) for value in channels.reshape(-1, 3)]
    if channels.ndim == 1:
        return hexes[0]
    return hexes


def from_hex(hexes):
    """Hex string or sequence of them -> (..., 3) linear sRGB."""
    if isinstance(hexes, str):
        single = True
        hexes = [hexes]
    else:
        single = False
    codes = [value.lstrip("#") for value in hexes]
    channels = np.array([[int(code[i : i + 2], 16) for i in (0, 2, 4)] for code in codes], dtype=float) / 255.0
    linear = srgb_to_linear_srgb(channels)
    if single:
        return linear[0]
    return linear
