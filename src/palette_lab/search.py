"""Encode a ringed palette as a parameter vector, score it, and search that space.

A *ring* is a set of colors sharing one Oklab lightness and one chroma, differing only
in hue. A *layout* says how the 12 colors split across rings: (12,) is one ring,
(6, 6) is two rings of six.

The score is the smallest CIEDE2000 distance over all 66 pairs. We maximize it, so the
palette's worst confusion is as mild as it can be.
"""

import itertools
from dataclasses import dataclass

import numpy as np
from cmaes import CMA

from palette_lab import color

N_COLORS = 12

LIGHTNESS_RANGE = (0.05, 0.98)
# A ring at rho=1 sits exactly on the gamut boundary at its worst hue. Below about 0.05
# every ring is near-gray and the search learns nothing, so the floor costs us nothing.
RHO_RANGE = (0.05, 1.0)
# Hue gaps come from a softmax. This bounds the logits, which bounds how lopsided the
# gaps can get: at +-4 the widest gap is e^8 times the narrowest, far past any optimum.
LOGIT_SCALE = 4.0

# Pure maximin is flat wherever the worst pair does not move, and CMA-ES stalls on flat
# ground. Adding a sliver of the mean tilts those plateaus. At 1e-3 it cannot outweigh a
# real change in the minimum, which is what we actually rank on.
TIEBREAK_WEIGHT = 1e-3

# Appended to a layout name when every ring takes the same chroma, as in "6+6:C".
SHARED_CHROMA_SUFFIX = ":C"


@dataclass(frozen=True)
class Layout:
    """How the 12 colors split across rings, and whether the rings share one chroma.

    With `shared_chroma`, all rings take a single C, capped by the worst hue anywhere in
    the palette rather than the worst hue on each ring. That is a real constraint, not a
    relabelling: a ring that could have carried more chroma gives it up.
    """

    sizes: tuple[int, ...]
    shared_chroma: bool = False

    def __post_init__(self):
        if sum(self.sizes) != N_COLORS:
            raise ValueError(f"ring sizes {self.sizes} must sum to {N_COLORS}")
        if any(size < 1 for size in self.sizes):
            raise ValueError(f"ring sizes {self.sizes} must all be positive")

    @property
    def name(self):
        name = "+".join(str(size) for size in self.sizes)
        if self.shared_chroma:
            return name + SHARED_CHROMA_SUFFIX
        return name

    @property
    def slug(self):
        """The name as a filename. `6+6:C` holds a colon, which Windows will not accept."""
        if self.shared_chroma:
            return self.name.replace(SHARED_CHROMA_SUFFIX, "-sharedC")
        return self.name

    @property
    def n_rings(self):
        return len(self.sizes)

    @property
    def n_chroma(self):
        """How many free chroma values the layout has: one shared, or one per ring."""
        if self.shared_chroma:
            return 1
        return self.n_rings

    @property
    def n_params(self):
        """A lightness and a phase per ring, a rho per chroma value, and a gap logit per color past a ring's first."""
        return 2 * self.n_rings + self.n_chroma + (N_COLORS - self.n_rings)

    @property
    def ring_of_color(self):
        """(12,) array giving each color's ring index."""
        return np.repeat(np.arange(self.n_rings), self.sizes)

    @property
    def chroma_of_color(self):
        """(12,) array giving each color's chroma slot. All zero when the rings share one."""
        if self.shared_chroma:
            return np.zeros(N_COLORS, dtype=int)
        return self.ring_of_color


def _softmax(logits):
    """Softmax over the last axis."""
    weights = np.exp(logits - logits.max(axis=-1, keepdims=True))
    return weights / weights.sum(axis=-1, keepdims=True)


def decode(unit_params, layout):
    """(batch, n_params) in [0, 1] -> ((batch, 12, 3) OKLCh, (batch, n_rings) lightness, chroma).

    Hues on a ring are a phase plus the running sum of gaps that a softmax forces to add
    to 360 degrees. Every permutation of a ring's hues describes the same palette, so a
    free-hue encoding would hand CMA-ES many copies of every solution to waste its budget
    on. This encoding has one representative per palette.

    Chroma is rho times the largest chroma the ring's *worst* hue can reach, so every
    decoded palette is inside sRGB by construction and the search needs no penalty term.
    """
    unit_params = np.atleast_2d(np.asarray(unit_params, dtype=float))
    batch = unit_params.shape[0]
    n_rings = layout.n_rings
    n_chroma = layout.n_chroma

    lightness = LIGHTNESS_RANGE[0] + unit_params[:, :n_rings] * (LIGHTNESS_RANGE[1] - LIGHTNESS_RANGE[0])
    rho = RHO_RANGE[0] + unit_params[:, n_rings : n_rings + n_chroma] * (RHO_RANGE[1] - RHO_RANGE[0])
    phase = unit_params[:, n_rings + n_chroma : 2 * n_rings + n_chroma] * 360.0

    hues = np.empty((batch, N_COLORS))
    cursor = 2 * n_rings + n_chroma
    start = 0
    for ring, size in enumerate(layout.sizes):
        free = unit_params[:, cursor : cursor + size - 1] * (2.0 * LOGIT_SCALE) - LOGIT_SCALE
        gaps = _softmax(np.concatenate([np.zeros((batch, 1)), free], axis=1)) * 360.0
        offsets = np.concatenate([np.zeros((batch, 1)), np.cumsum(gaps[:, :-1], axis=1)], axis=1)
        hues[:, start : start + size] = phase[:, ring : ring + 1] + offsets
        cursor += size - 1
        start += size

    ring_of_color = layout.ring_of_color
    chroma_of_color = layout.chroma_of_color
    per_color_lightness = lightness[:, ring_of_color]

    # A chroma slot is capped by the worst hue it has to cover. That is the ring's own
    # hues normally, and every hue in the palette when the rings share one chroma.
    ceiling = color.max_chroma(per_color_lightness, hues)
    slot_ceiling = np.stack([ceiling[:, chroma_of_color == slot].min(axis=1) for slot in range(n_chroma)], axis=1)
    per_color_chroma = (rho * slot_ceiling)[:, chroma_of_color]

    oklch = np.stack([per_color_lightness, per_color_chroma, hues % 360.0], axis=-1)
    # Report chroma per ring, whatever the slot layout, so callers never branch on it.
    first_of_ring = np.cumsum((0,) + layout.sizes)[:-1]
    return oklch, lightness, per_color_chroma[:, first_of_ring]


def delta_e_stats(oklch, indices=None):
    """(batch, 12, 3) OKLCh -> (minimum, mean) CIEDE2000 over the 66 pairs, per batch row."""
    lab = color.oklab_to_lab(color.oklch_to_oklab(oklch))
    pairs = color.pairwise_delta_e(lab, indices)
    return pairs.min(axis=-1), pairs.mean(axis=-1)


def score(unit_params, layout, indices=None):
    """(batch, n_params) -> (batch,) score to maximize."""
    oklch, _, _ = decode(unit_params, layout)
    minimum, mean = delta_e_stats(oklch, indices)
    return minimum + TIEBREAK_WEIGHT * mean


def equal_spacing_baseline(layout, n_lightness=97):
    """Best minimum delta-E with evenly spaced hues and aligned rings, over a lightness grid.

    This is a floor, not the best even-spacing palette. Rotating one ring against the
    other beats it, by 3.8% on 6+6. The search has to clear this floor or it did not earn
    its runtime, and it clears it by about 28%. Returns the value and its parameters.
    """
    grid = np.linspace(LIGHTNESS_RANGE[0], LIGHTNESS_RANGE[1], n_lightness)
    n_rings = layout.n_rings
    span = LIGHTNESS_RANGE[1] - LIGHTNESS_RANGE[0]

    candidates = []
    for lightnesses in itertools.combinations_with_replacement(grid, n_rings):
        params = np.zeros(layout.n_params)
        for ring, value in enumerate(lightnesses):
            params[ring] = (value - LIGHTNESS_RANGE[0]) / span
        # Chroma pushed to the gamut limit, and equal gaps, which are equal logits. 0.5
        # maps to logit 0. Every phase stays 0, so the rings sit aligned.
        params[n_rings : n_rings + layout.n_chroma] = 1.0
        params[2 * n_rings + layout.n_chroma :] = 0.5
        candidates.append(params)

    candidates = np.array(candidates)
    oklch, _, _ = decode(candidates, layout)
    minimum, _ = delta_e_stats(oklch)
    best = int(np.argmax(minimum))
    return float(minimum[best]), candidates[best]


def search_layout(layout, restarts=12, max_evaluations=4000, seed=0, verbose=False):
    """Run CMA-ES with restarts. Returns (parameter vectors best first, baseline value).

    Each generation is decoded and scored in one batch, so the color math runs once per
    generation rather than once per candidate. That is where the speed comes from.
    """
    indices = color.triu_indices(N_COLORS)
    bounds = np.tile([0.0, 1.0], (layout.n_params, 1))

    baseline_value, baseline_params = equal_spacing_baseline(layout)
    found = [(float(score(baseline_params[None, :], layout, indices)[0]), baseline_params)]

    for restart in range(restarts):
        rng = np.random.default_rng(seed * 1000 + restart)
        # Restart 0 starts from the middle of the box; the rest start anywhere, so the
        # restarts explore different basins instead of re-running the same descent.
        if restart == 0:
            mean = np.full(layout.n_params, 0.5)
        else:
            mean = rng.uniform(0.15, 0.85, layout.n_params)

        optimizer = CMA(mean=mean, sigma=0.25, bounds=bounds, seed=int(rng.integers(1 << 31)))
        used = 0
        while used < max_evaluations and not optimizer.should_stop():
            batch = np.array([optimizer.ask() for _ in range(optimizer.population_size)])
            values = score(batch, layout, indices)
            optimizer.tell([(batch[i], -float(values[i])) for i in range(len(batch))])
            used += len(batch)
            best = int(np.argmax(values))
            found.append((float(values[best]), batch[best].copy()))

        if verbose:
            print(f"  {layout.name} restart {restart:2d}: best {max(v for v, _ in found):8.4f} after {used} evals")

    found.sort(key=lambda item: -item[0])
    return [params for _, params in found], baseline_value
