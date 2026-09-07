"""Shared fixtures.

`EXPERIMENTS` restates the three layouts the scripts under `scripts/` declare. That is a
second copy of the list, which `test_scripts.py` closes by asserting the scripts agree
with it.
"""

import matplotlib
import numpy as np
import pytest

# Imported before every test module, so this is where the headless backend gets set.
matplotlib.use("Agg")

from palette_lab import color
from palette_lab.palette import Palette
from palette_lab.search import Layout

EXPERIMENTS = [
    Layout((6, 6)),
    Layout((5, 7)),
    Layout((6, 6), shared_chroma=True),
    Layout((5, 7), shared_chroma=True),
    Layout((5, 5, 2), chroma_groups=(0, 1, 1), lightness_floor=0.45),
    Layout((1,) * 12, chroma_groups=(0,) * 12, lightness_floor=0.60, lightness_ceiling=0.85, label="bright12"),
]


def ring_lightnesses(layout, count=None):
    """Evenly spaced lightnesses for a layout's rings, inside whatever range it allows.

    Spread over the middle of the range rather than its edges, so a hand-built palette is
    never so near the gamut boundary that a ring collapses to no chroma.
    """
    low, high = layout.lightness_range
    span = high - low
    return tuple(np.linspace(low + 0.25 * span, low + 0.75 * span, count or layout.n_rings))


def build_palette(layout, lightnesses=None, seed=0):
    """A valid palette for `layout`, built by hand so tests do not depend on a search.

    Rings sit at the given lightnesses with hues evenly spaced and chroma at the gamut
    limit, which is exactly the invariant `verify` checks. Chroma is capped per slot, so
    rings sharing a slot get the worst ceiling among all of them, whether that slot holds
    one ring, two, or every ring in the layout.
    """
    if lightnesses is None:
        lightnesses = ring_lightnesses(layout)
    oklch = np.zeros((12, 3))
    ring_of_color = layout.ring_of_color
    chroma_of_color = layout.chroma_of_color
    hues_by_ring = []
    for ring, size in enumerate(layout.sizes):
        hues_by_ring.append(np.linspace(0.0, 360.0, size, endpoint=False) + 30.0 * ring)

    every_lightness = np.concatenate([np.full(size, lightnesses[ring]) for ring, size in enumerate(layout.sizes)])
    every_hue = np.concatenate(hues_by_ring)
    ceilings = [
        color.max_chroma(every_lightness[chroma_of_color == slot], every_hue[chroma_of_color == slot]).min()
        for slot in range(layout.n_chroma)
    ]

    for ring, size in enumerate(layout.sizes):
        members = ring_of_color == ring
        ceiling = ceilings[layout.groups[ring]]
        oklch[members] = np.stack(
            [np.full(size, lightnesses[ring]), np.full(size, ceiling), hues_by_ring[ring]], axis=-1
        )
    return Palette(layout=layout, oklch=oklch, config={"gamut": "sRGB", "restarts": 1, "seed": seed})


@pytest.fixture(params=EXPERIMENTS, ids=lambda layout: layout.name)
def experiment_layout(request):
    return request.param


@pytest.fixture
def palette(experiment_layout):
    return build_palette(experiment_layout)
