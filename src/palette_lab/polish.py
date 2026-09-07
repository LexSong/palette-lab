"""Refine a CMA-ES solution with SLSQP on the epigraph form of the maximin problem.

CMA-ES finds the right basin but stops loosely, because the score it climbs is a `min`
over 66 pairs and that surface has a kink wherever the worst pair changes. The epigraph
form removes the kink. Introduce `t`, then

    maximize   t
    subject to dE00(i, j) >= t                    for all 66 pairs
               linear sRGB channels in [0, 1]     for all 12 colors

Every constraint is smooth, so SLSQP converges properly and gives the exact local
optimum of the basin CMA-ES landed in.

That leaves the palette underdetermined. A color in no binding pair does not appear in
the active constraints, so the objective is flat in its direction and SLSQP stops wherever
its iteration lands. `6+6:C` has one such color and `5+7` has five. So there is a second
stage: hold every pair at the `t` the first stage reached, then maximize the mean
CIEDE2000. That pins the free colors down, makes the result reproducible, and improves
average separation.

The two stages are lexicographic, not a weighted sum. `min + w * mean` would trade real
minimum for mean -- at w=1e-3 and a mean near 43, giving up 0.001 of the minimum to gain
1.0 of the mean pays -- and the minimum is the number this repo exists to maximize.
Freezing `t` makes that trade impossible.

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

# How far the second stage may fall below the first stage's minimum before we reject it.
# Freezing t should hold the minimum exactly, so this only absorbs SLSQP's own tolerance.
MINIMUM_TOLERANCE = 1e-9


def pack(lightness, chroma, hues, t, layout):
    """Ring lightness, ring chroma, 12 hues and t -> the scaled SLSQP variable vector.

    There is one chroma variable per slot, not per ring, so rings sharing a slot collapse
    to the first ring that uses it. They are equal by construction, and `unpack` spreads
    them back over the rings through `chroma_of_color`.
    """
    chroma = np.asarray(chroma, dtype=float)
    groups = layout.groups
    chroma = np.array([chroma[groups.index(slot)] for slot in range(layout.n_chroma)])
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


def _mean_separation(variables, layout, indices):
    """(batch, n_var) -> (batch,) mean CIEDE2000 over the 66 pairs, on the constraint scale.

    Same color path as `_constraints`, so the second stage measures exactly what the first
    stage constrained.
    """
    _, oklch = unpack(variables, layout)
    linear = color.oklab_to_linear_srgb(color.oklch_to_oklab(oklch))
    return color.pairwise_delta_e(color.linear_srgb_to_lab(linear), indices).mean(axis=-1) / DELTA_E_SCALE


def _separation_stats(oklch, indices):
    """(12, 3) OKLCh -> (minimum, mean) CIEDE2000, from linear sRGB like everything else."""
    lab = color.oklab_to_lab(color.oklch_to_oklab(oklch))
    pairs = color.pairwise_delta_e(lab, indices)
    return float(pairs.min()), float(pairs.mean())


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

    Two stages: maximize the worst pair, then maximize the mean without letting the worst
    pair move. Each stage falls back to what came before it if SLSQP fails or makes things
    worse, so calling this can only help.
    """
    indices = color.triu_indices(N_COLORS)
    oklch, lightness, chroma = decode(unit_params[None, :], layout)
    oklch = oklch[0]

    start_minimum, start_mean = _separation_stats(oklch, indices)
    variables = pack(lightness[0], chroma[0], oklch[:, 2], start_minimum, layout)

    def constraint_values(batch):
        return _constraints(batch, layout, indices)

    constraints = [
        {
            "type": "ineq",
            "fun": lambda z: constraint_values(z[None, :])[0],
            "jac": lambda z: _jacobian(constraint_values, z),
        }
    ]
    # Refinement runs after the search, and nothing re-checks the layout's lightness range
    # afterwards, so the bounds have to carry both ends of it here too.
    low, high = layout.lightness_range
    lightness_bounds = (max(LIGHTNESS_BOUNDS[0], low), min(LIGHTNESS_BOUNDS[1], high))
    bounds = (
        [(0.0, 1.0)]
        + [lightness_bounds] * layout.n_rings
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
        constraints=constraints,
        options={"maxiter": max_iterations, "ftol": 1e-12},
    )

    _, refined = unpack(result.x[None, :], layout)
    refined = clamp_into_gamut(refined[0], layout)
    best_oklch, best_minimum, best_mean = oklch, start_minimum, start_mean
    best_variables = variables
    refined_minimum, refined_mean = _separation_stats(refined, indices)
    if refined_minimum > start_minimum:
        best_oklch, best_minimum, best_mean = refined, refined_minimum, refined_mean
        best_variables = result.x

    # Freeze t at the minimum the palette actually reaches, so every pair stays at or above
    # it, and spend the remaining freedom on the mean. Equal bounds pin the variable;
    # SLSQP simply never moves it.
    frozen = best_minimum / DELTA_E_SCALE
    spread = minimize(
        lambda z: -_mean_separation(z[None, :], layout, indices)[0],
        np.concatenate([[frozen], best_variables[1:]]),
        jac=lambda z: -_jacobian(lambda batch: _mean_separation(batch, layout, indices), z),
        method="SLSQP",
        bounds=[(frozen, frozen)] + bounds[1:],
        constraints=constraints,
        options={"maxiter": max_iterations, "ftol": 1e-12},
    )

    _, spread_oklch = unpack(spread.x[None, :], layout)
    spread_oklch = clamp_into_gamut(spread_oklch[0], layout)
    spread_minimum, spread_mean = _separation_stats(spread_oklch, indices)
    if spread_minimum >= best_minimum - MINIMUM_TOLERANCE and spread_mean > best_mean:
        return sort_hues_within_rings(spread_oklch, layout), spread_minimum
    return sort_hues_within_rings(best_oklch, layout), best_minimum
