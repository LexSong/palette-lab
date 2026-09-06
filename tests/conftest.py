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

EXPERIMENTS = [Layout((6, 6)), Layout((5, 7)), Layout((6, 6), shared_chroma=True)]


def build_palette(layout, lightnesses=(0.55, 0.80), seed=0):
    """A valid palette for `layout`, built by hand so tests do not depend on a search.

    Rings sit at the given lightnesses with hues evenly spaced and chroma at the gamut
    limit, which is exactly the invariant `verify` checks.
    """
    oklch = np.zeros((12, 3))
    ring_of_color = layout.ring_of_color
    hues_by_ring = []
    for ring, size in enumerate(layout.sizes):
        hues_by_ring.append(np.linspace(0.0, 360.0, size, endpoint=False) + 30.0 * ring)

    if layout.shared_chroma:
        every_lightness = np.concatenate([np.full(size, lightnesses[ring]) for ring, size in enumerate(layout.sizes)])
        ceilings = [color.max_chroma(every_lightness, np.concatenate(hues_by_ring)).min()] * layout.n_rings
    else:
        ceilings = [
            color.max_chroma(np.full(size, lightnesses[ring]), hues_by_ring[ring]).min()
            for ring, size in enumerate(layout.sizes)
        ]

    for ring, size in enumerate(layout.sizes):
        members = ring_of_color == ring
        oklch[members] = np.stack(
            [np.full(size, lightnesses[ring]), np.full(size, ceilings[ring]), hues_by_ring[ring]], axis=-1
        )
    return Palette(layout=layout, oklch=oklch, config={"gamut": "sRGB", "restarts": 1, "seed": seed})


@pytest.fixture(params=EXPERIMENTS, ids=lambda layout: layout.name)
def experiment_layout(request):
    return request.param


@pytest.fixture
def palette(experiment_layout):
    return build_palette(experiment_layout)
