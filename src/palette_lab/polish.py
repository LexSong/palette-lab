"""Refine a CMA-ES solution with SLSQP on the epigraph form of the maximin problem.

CMA-ES finds the right basin but stops loosely, because the score it climbs is a `min`
over 66 pairs and that surface has a kink wherever the worst pair changes. The epigraph
form removes the kink. Introduce `t`, then

    maximize   t
    subject to dE00(i, j) >= t                    for all 66 pairs
               linear sRGB channels in [0, 1]     for all 12 colors

Every constraint is smooth, so SLSQP converges properly and gives the exact local
optimum of the basin CMA-ES landed in.

The search parameterization does not survive the move: it pins ring chroma to
`rho * min(max_chroma over the ring)`, and that `min` is another kink. Here chroma is a
free variable and the gamut is an explicit constraint instead.
"""

import numpy as np
from scipy.optimize import minimize

from palette_lab import color
from palette_lab.search import N_COLORS
from palette_lab.search import decode

# SLSQP takes one finite-difference step for every variable, so the variables should
# share a scale. Lightness is already 0-1; these bring chroma, hue and t alongside it.
CHROMA_SCALE = 4.0
HUE_SCALE = 360.0
DELTA_E_SCALE = 100.0

# Central differences in the scaled space. Function values are order 1 there, so this
# sits near the sqrt(machine epsilon) sweet spot.
FD_STEP = 1e-6

LIGHTNESS_BOUNDS = (0.005, 0.999)


def pack(lightness, chroma, hues, t, layout):
    """Ring lightness, ring chroma, 12 hues and t -> the scaled SLSQP variable vector.

    A shared-chroma layout has one chroma variable, so the per-ring values collapse to
    their first entry. They are equal by construction, and `polish` re-derives the rest.
    """
    chroma = np.asarray(chroma, dtype=float)
    if layout.shared_chroma:
        chroma = chroma[:1]
    return np.concatenate(
        [
            [t / DELTA_E_SCALE],
            np.asarray(lightness, dtype=float),
            chroma * CHROMA_SCALE,
            np.asarray(hues, dtype=float) / HUE_SCALE,
        ]
    )


def unpack(variables, layout):
    """(batch, n_var) scaled variables -> ((batch,) t, (batch, 12, 3) OKLCh)."""
    variables = np.atleast_2d(np.asarray(variables, dtype=float))
    n_rings = layout.n_rings
    n_chroma = layout.n_chroma
    t = variables[:, 0] * DELTA_E_SCALE
    lightness = variables[:, 1 : 1 + n_rings]
    chroma = variables[:, 1 + n_rings : 1 + n_rings + n_chroma] / CHROMA_SCALE
    hues = variables[:, 1 + n_rings + n_chroma :] * HUE_SCALE

    oklch = np.stack([lightness[:, layout.ring_of_color], chroma[:, layout.chroma_of_color], hues], axis=-1)
    return t, oklch


def _constraints(variables, layout, indices):
    """(batch, n_var) -> (batch, 66 + 72) constraint values, all of which must be >= 0."""
    t, oklch = unpack(variables, layout)
    oklab = color.oklch_to_oklab(oklch)
    linear = color.oklab_to_linear_srgb(oklab)

    separation = color.pairwise_delta_e(color.linear_srgb_to_lab(linear), indices) - t[:, None]
    floor = linear.reshape(linear.shape[0], -1)
    ceiling = 1.0 - floor
    return np.concatenate([separation / DELTA_E_SCALE, floor, ceiling], axis=1)


def _jacobian(function, variables):
    """Central-difference Jacobian of a batched vector function. One batched call."""
    variables = np.asarray(variables, dtype=float)
    n_var = variables.shape[0]
    steps = FD_STEP * np.eye(n_var)
    probes = np.concatenate([variables + steps, variables - steps], axis=0)
    values = function(probes)
    forward, backward = values[:n_var], values[n_var:]
    return ((forward - backward) / (2.0 * FD_STEP)).T


def clamp_into_gamut(oklch, layout):
    """Shrink each chroma slot to the largest value its worst hue can hold.

    SLSQP satisfies the gamut constraints to its own tolerance, which can leave a color
    a few 1e-9 outside. This makes the result exactly feasible. A shared-chroma layout has
    one slot covering all 12 colors, so it clamps to the worst hue in the whole palette.
    """
    oklch = np.array(oklch, dtype=float)
    chroma_of_color = layout.chroma_of_color
    for slot in range(layout.n_chroma):
        members = chroma_of_color == slot
        ceiling = color.max_chroma(oklch[members, 0], oklch[members, 2]).min()
        oklch[members, 1] = min(oklch[members, 1].min(), ceiling)
    return oklch


def sort_hues_within_rings(oklch, layout):
    """Order each ring's colors by hue. Presentation only, the palette is unchanged."""
    oklch = np.array(oklch, dtype=float)
    ring_of_color = layout.ring_of_color
    for ring in range(layout.n_rings):
        members = np.flatnonzero(ring_of_color == ring)
        oklch[members] = oklch[members][np.argsort(oklch[members, 2])]
    return oklch


def polish(unit_params, layout, max_iterations=300):
    """Refine one CMA-ES parameter vector. Returns (12, 3) OKLCh and its minimum delta-E.

    Falls back to the unrefined palette if SLSQP fails or makes it worse, so calling this
    can only help.
    """
    indices = color.triu_indices(N_COLORS)
    oklch, lightness, chroma = decode(unit_params[None, :], layout)
    oklch = oklch[0]

    start_minimum = float(color.pairwise_delta_e(color.oklab_to_lab(color.oklch_to_oklab(oklch)), indices).min())
    variables = pack(lightness[0], chroma[0], oklch[:, 2], start_minimum, layout)

    def constraint_values(batch):
        return _constraints(batch, layout, indices)

    bounds = (
        [(0.0, 1.0)]
        + [LIGHTNESS_BOUNDS] * layout.n_rings
        + [(0.0, color.CHROMA_CEILING * CHROMA_SCALE)] * layout.n_chroma
        + [(None, None)] * N_COLORS
    )
    objective_gradient = np.zeros(len(variables))
    objective_gradient[0] = -1.0

    result = minimize(
        lambda z: -z[0],
        variables,
        jac=lambda _z: objective_gradient,
        method="SLSQP",
        bounds=bounds,
        constraints=[
            {
                "type": "ineq",
                "fun": lambda z: constraint_values(z[None, :])[0],
                "jac": lambda z: _jacobian(constraint_values, z),
            }
        ],
        options={"maxiter": max_iterations, "ftol": 1e-12},
    )

    _, refined = unpack(result.x[None, :], layout)
    refined = clamp_into_gamut(refined[0], layout)
    refined_minimum = float(color.pairwise_delta_e(color.oklab_to_lab(color.oklch_to_oklab(refined)), indices).min())

    if refined_minimum > start_minimum:
        return sort_hues_within_rings(refined, layout), refined_minimum
    return sort_hues_within_rings(oklch, layout), start_minimum
