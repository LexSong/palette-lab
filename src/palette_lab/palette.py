"""The palette record, and the JSON one experiment writes.

The file holds what cannot be recomputed: the layout, the 12 OKLCh triples, the settings
that produced them, and the two headline numbers. Everything else — hex, the CIEDE2000
matrix, which pairs are binding — hangs off `Palette` and is derived on demand, about
1 ms for the lot. Deriving beats storing here, because a stored number can drift from the
palette it claims to describe and a derived one cannot.
"""

import datetime
import json
from dataclasses import dataclass
from dataclasses import field
from functools import cached_property

import numpy as np

from palette_lab import color
from palette_lab.search import N_COLORS
from palette_lab.search import Layout

SCHEMA_VERSION = 3

# How close to the minimum a pair has to sit to count as binding. CIEDE2000 values run
# 15-70 here, so 0.05 is tight enough that only genuinely pinned pairs qualify.
BINDING_TOLERANCE = 0.05

# Decimal places the file keeps for each OKLCh component.
QUANTIZATION_DIGITS = 6


@dataclass(frozen=True)
class Palette:
    """12 colors on rings, plus the settings that found them.

    `cached_property` writes into the instance `__dict__` directly, so it works on a
    frozen dataclass. Nothing here mutates `oklch` after construction.
    """

    layout: Layout
    oklch: np.ndarray
    config: dict = field(default_factory=dict)
    generated: str = ""

    def __post_init__(self):
        oklch = np.asarray(self.oklch, dtype=float)
        if oklch.shape != (N_COLORS, 3):
            raise ValueError(f"expected a ({N_COLORS}, 3) OKLCh array, got {oklch.shape}")
        object.__setattr__(self, "oklch", oklch)
        if not self.generated:
            object.__setattr__(self, "generated", datetime.datetime.now().astimezone().isoformat(timespec="seconds"))

    @cached_property
    def oklab(self):
        return color.oklch_to_oklab(self.oklch)

    @cached_property
    def linear_srgb(self):
        return color.oklab_to_linear_srgb(self.oklab)

    @cached_property
    def hexes(self):
        return color.to_hex(self.linear_srgb)

    @cached_property
    def lab(self):
        """CIE Lab, from linear sRGB rather than from Oklab, so it matches what ships."""
        return color.linear_srgb_to_lab(self.linear_srgb)

    @cached_property
    def delta_e_matrix(self):
        return color.delta_e_matrix(self.lab)

    @cached_property
    def pairs(self):
        """The 66 upper-triangle CIEDE2000 values, and the indices they came from."""
        rows, cols = color.triu_indices(N_COLORS)
        return self.delta_e_matrix[rows, cols], rows, cols

    @cached_property
    def min_delta_e(self):
        return float(self.pairs[0].min())

    @cached_property
    def mean_delta_e(self):
        return float(self.pairs[0].mean())

    @cached_property
    def min_delta_e_quantized(self):
        """The separation that survives 8-bit hex, which is what a UI actually ships."""
        lab = color.linear_srgb_to_lab(color.from_hex(self.hexes))
        return float(color.pairwise_delta_e(lab).min())

    @cached_property
    def binding_pairs(self):
        """Every pair pinned at the minimum, not just the argmin.

        A converged maximin holds many pairs there at once, and together they are what
        stops the palette spreading further. The argmin is one arbitrary member.
        """
        values, rows, cols = self.pairs
        at_minimum = np.flatnonzero(values <= values.min() + BINDING_TOLERANCE)
        return [(int(rows[k]), int(cols[k])) for k in at_minimum]

    @cached_property
    def rings(self):
        """[(L, C)] per ring. Every color on a ring shares both, so the first one speaks for it."""
        ring_of_color = self.layout.ring_of_color
        return [
            (float(self.oklch[ring_of_color == ring, 0][0]), float(self.oklch[ring_of_color == ring, 1][0]))
            for ring in range(self.layout.n_rings)
        ]

    def gamut_excess(self):
        """How far the worst channel of the worst color falls outside sRGB. Zero is good."""
        return float(color.gamut_excess(self.linear_srgb).max())


def quantize(palette):
    """Round OKLCh to the precision the file stores, so what loads back is what was saved.

    A ring sits exactly on the gamut boundary, so rounding cannot be naive. Lightness and
    hue round to nearest, and then chroma is re-derived against those rounded values —
    rounding L moves the boundary, sometimes by more than one grid step, so flooring the
    original chroma is not enough on a high-chroma ring. The result is floored onto the
    grid, which can only move it inward. It costs at most 1e-6 of chroma, far below an
    8-bit step.
    """
    scale = 10.0**QUANTIZATION_DIGITS
    oklch = np.array(palette.oklch, dtype=float)
    oklch[:, 0] = np.round(oklch[:, 0] * scale) / scale
    oklch[:, 2] = np.round(oklch[:, 2] * scale) / scale

    chroma_of_color = palette.layout.chroma_of_color
    for slot in range(palette.layout.n_chroma):
        members = chroma_of_color == slot
        ceiling = float(color.max_chroma(oklch[members, 0], oklch[members, 2]).min())
        oklch[members, 1] = np.floor(min(float(oklch[members, 1].min()), ceiling) * scale) / scale

    return Palette(layout=palette.layout, oklch=oklch, config=palette.config, generated=palette.generated)


def to_document(palette):
    """The dict that gets written. Derived values stay out, apart from the two headlines.

    Everything is derived from the *quantized* palette, so the two stored numbers are
    exactly what a reader recomputes after loading.
    """
    # Checked before quantizing, because quantize clamps chroma to the gamut and would
    # otherwise silently rescue a palette that is wrong by far more than rounding.
    excess = palette.gamut_excess()
    if excess > 0.0:
        raise ValueError(f"{palette.layout.name} has an out-of-gamut color, excess {excess:.3e}")

    palette = quantize(palette)
    excess = palette.gamut_excess()
    if excess > 0.0:
        raise AssertionError(f"{palette.layout.name} left the gamut during quantization, excess {excess:.3e}")

    ring_of_color = palette.layout.ring_of_color
    return {
        "schema": SCHEMA_VERSION,
        "generated": palette.generated,
        "experiment": {
            "layout": palette.layout.name,
            "sizes": list(palette.layout.sizes),
            "shared_chroma": palette.layout.shared_chroma,
            **palette.config,
        },
        "result": {
            "min_de2000": round(palette.min_delta_e, 4),
            "min_de2000_quantized": round(palette.min_delta_e_quantized, 4),
        },
        "rings": [{"L": lightness, "C": chroma} for lightness, chroma in palette.rings],
        "colors": [
            {
                "ring": int(ring_of_color[index]),
                "hex": palette.hexes[index],
                "oklch": list(palette.oklch[index]),
            }
            for index in range(N_COLORS)
        ],
    }


def from_document(document):
    if document.get("schema") != SCHEMA_VERSION:
        raise ValueError(f"schema {document.get('schema')}, expected {SCHEMA_VERSION}")
    experiment = dict(document["experiment"])
    layout = Layout(tuple(experiment.pop("sizes")), experiment.pop("shared_chroma"))
    experiment.pop("layout", None)
    oklch = np.array([entry["oklch"] for entry in document["colors"]], dtype=float)
    return Palette(layout=layout, oklch=oklch, config=experiment, generated=document["generated"])


def save(palette, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_document(palette), indent=2) + "\n", encoding="utf-8")


def load(path):
    return from_document(json.loads(path.read_text(encoding="utf-8")))
