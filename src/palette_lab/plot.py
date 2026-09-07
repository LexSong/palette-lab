"""The figure: the a/b wheel, the CIEDE2000 matrix, and a swatch strip.

Everything here reads a `Palette` and derives what it needs. Both the experiment scripts
and `scripts/visualize_palette.py` call `build_figure`.
"""

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Circle
from matplotlib.patches import Rectangle

from palette_lab import color

# One marker per ring, so which ring a point belongs to survives in grayscale and in
# print. The a/b view drops lightness, which is the only thing separating the rings.
RING_MARKERS = ["o", "D", "s", "^"]

CHROMA_GRID = np.arange(0.04, 0.36, 0.04)
HUE_SPOKES = np.arange(0, 360, 30)

THEMES = {
    "light": {
        "surface": "#ffffff",
        "ink": "#1c1e21",
        "muted": "#6b7280",
        "hairline": "#e6e8eb",
        "rule": "#c9ced6",
        # Low delta-E is the problem, so it gets the loud end.
        "delta_ramp": [
            (0.00, "#9d130c"),
            (0.07, "#c93a28"),
            (0.18, "#e58876"),
            (0.32, "#f2cac0"),
            (0.45, "#efeeeb"),
            (1.00, "#f6f7f8"),
        ],
    },
    "dark": {
        "surface": "#15171c",
        "ink": "#e9eaee",
        "muted": "#8f96a3",
        "hairline": "#282c34",
        "rule": "#3a4049",
        # Stepped against the dark surface, not flipped from the light ramp.
        "delta_ramp": [
            (0.00, "#ff6a51"),
            (0.07, "#e04a34"),
            (0.18, "#a03a2a"),
            (0.32, "#5c3028"),
            (0.45, "#262a31"),
            (1.00, "#31343a"),
        ],
    },
}

# The stops above are bunched at the bottom on purpose. Values run about 25 to 65 here,
# and everything past roughly 38 is comfortable, so spreading red evenly would paint the
# whole matrix alarming. Red is spent on the bottom third; the ramp is neutral by 0.45 of
# the range and only drifts after that.
#
# Cells below this fraction of the range are saturated enough to need surface-colored
# text. That holds in both themes: light mode is dark red down there, dark mode is bright
# orange, and each contrasts with its own surface.
SATURATED_CELL_FRACTION = 0.11


def theme_for(dark=False):
    if dark:
        return THEMES["dark"]
    return THEMES["light"]


def emptiest_direction(hues, candidates=720):
    """The angle furthest from every hue in the palette.

    The chroma radius labels stack along one spoke. Which spoke is free depends on the
    palette, so we find it rather than fixing it and hoping.
    """
    probes = np.linspace(0.0, 360.0, candidates, endpoint=False)
    separation = np.abs(probes[:, None] - np.asarray(hues)[None, :])
    return float(probes[np.argmax(np.minimum(separation, 360.0 - separation).min(axis=1))])


def draw_wheel(axes, palette, theme):
    """Top-down view in the Oklab a/b plane. Lightness is deliberately dropped."""
    oklch = palette.oklch
    hexes = palette.hexes
    rings = palette.rings
    ring_of_color = palette.layout.ring_of_color

    # The sRGB boundary at each ring's lightness. A ring stops where it touches this
    # curve, so the curve explains the chroma the optimizer settled on. Showing all of it
    # also shows the headroom the worst hue on the ring costs the others.
    boundary_hues = np.linspace(0, 360, 721)
    radians = np.radians(boundary_hues)
    boundaries = [color.max_chroma(np.full_like(boundary_hues, lightness), boundary_hues) for lightness, _ in rings]
    limit = max(max(bound.max() for bound in boundaries) * 1.03, max(chroma for _, chroma in rings) * 1.45)

    tick_angle = np.radians(emptiest_direction(oklch[:, 2]))
    for radius in CHROMA_GRID[CHROMA_GRID <= limit]:
        axes.add_patch(Circle((0, 0), radius, fill=False, ec=theme["hairline"], lw=0.6, zorder=0))
        axes.text(
            radius * np.cos(tick_angle),
            radius * np.sin(tick_angle),
            f"{radius:.2f}",
            fontsize=6.5,
            color=theme["muted"],
            ha="center",
            va="center",
            zorder=3,
            bbox={"facecolor": theme["surface"], "edgecolor": "none", "pad": 0.8},
        )
    for angle in np.radians(HUE_SPOKES):
        axes.plot([0, limit * np.cos(angle)], [0, limit * np.sin(angle)], color=theme["hairline"], lw=0.6, zorder=0)

    axes.axhline(0, color=theme["rule"], lw=0.8, zorder=1)
    axes.axvline(0, color=theme["rule"], lw=0.8, zorder=1)

    for (lightness, chroma), boundary in zip(rings, boundaries, strict=True):
        axes.plot(boundary * np.cos(radians), boundary * np.sin(radians), color=theme["rule"], lw=0.9, zorder=1)
        axes.add_patch(Circle((0, 0), chroma, fill=False, ec=theme["rule"], lw=0.9, zorder=2))
        widest = int(np.argmax(boundary))
        axes.text(
            boundary[widest] * np.cos(radians[widest]) * 0.86,
            boundary[widest] * np.sin(radians[widest]) * 0.86,
            f"sRGB limit at L={lightness:.3f}",
            fontsize=7,
            color=theme["muted"],
            ha="center",
            va="center",
            zorder=3,
            bbox={"facecolor": theme["surface"], "edgecolor": "none", "pad": 1.0},
        )

    # Two rings at similar chroma put their markers almost on top of each other, because
    # what separates them is the lightness this view drops. Each ring's index labels sit
    # at their own radius so they never collide.
    for index in range(len(hexes)):
        ring = int(ring_of_color[index])
        angle = np.radians(oklch[index, 2])
        chroma = oklch[index, 1]
        axes.scatter(
            chroma * np.cos(angle),
            chroma * np.sin(angle),
            s=360 - 110 * ring,
            marker=RING_MARKERS[ring % len(RING_MARKERS)],
            c=hexes[index],
            edgecolors=theme["surface"],
            linewidths=2.0,
            zorder=4 + ring,
        )
        label_radius = chroma + limit * (0.10 + 0.075 * ring)
        axes.text(
            label_radius * np.cos(angle),
            label_radius * np.sin(angle),
            str(index),
            fontsize=8,
            fontweight="bold",
            color=theme["ink"],
            ha="center",
            va="center",
            zorder=9,
        )

    groups = palette.layout.groups

    def shared_with(ring):
        """Which other rings draw this ring's chroma from the same slot."""
        others = [other for other in range(len(groups)) if other != ring and groups[other] == groups[ring]]
        if not others:
            return ""
        return f" (shared with {', '.join(str(other) for other in others)})"

    handles = [
        Line2D(
            [],
            [],
            marker=RING_MARKERS[ring % len(RING_MARKERS)],
            linestyle="none",
            markersize=9,
            markerfacecolor=theme["muted"],
            markeredgecolor=theme["surface"],
            label=f"ring {ring}: {size} colors, L={lightness:.3f}, C={chroma:.3f}{shared_with(ring)}",
        )
        for ring, (size, (lightness, chroma)) in enumerate(zip(palette.layout.sizes, rings, strict=True))
    ]
    axes.legend(handles=handles, loc="upper left", fontsize=8, frameon=False, labelcolor=theme["ink"]).set_zorder(10)

    axes.set_xlim(-limit, limit)
    axes.set_ylim(-limit, limit)
    axes.set_aspect("equal")
    axes.set_xlabel("Oklab a   (green  ←  →  red)", fontsize=9, color=theme["muted"])
    axes.set_ylabel("Oklab b   (blue  ←  →  yellow)", fontsize=9, color=theme["muted"])
    axes.set_title(f"Palette on the Oklab a/b plane  —  {palette.layout.name}", fontsize=11, color=theme["ink"])
    style_axes(axes, theme)


def draw_swatches(axes, palette, theme):
    """The palette in order, with black and white samples over each for a legibility read."""
    hexes = palette.hexes
    ring_of_color = palette.layout.ring_of_color
    axes.set_xlim(0, len(hexes))
    axes.set_ylim(0, 1)
    axes.axis("off")
    axes.set_title("Swatches, in palette order", fontsize=11, color=theme["ink"], loc="left", pad=8)

    for index, value in enumerate(hexes):
        axes.add_patch(Rectangle((index + 0.02, 0.34), 0.96, 0.66, facecolor=value, edgecolor="none"))
        axes.text(index + 0.5, 0.86, "Aa", fontsize=11, color="#000000", ha="center", va="center")
        axes.text(index + 0.5, 0.60, "Aa", fontsize=11, color="#ffffff", ha="center", va="center")
        # The index has to stay readable on every swatch, so it takes whichever of black
        # or white the swatch's own lightness calls for. The "Aa" pair above is the
        # legibility test; this label is not part of it.
        lightness, chroma, hue = palette.oklch[index]
        if lightness > 0.62:
            ink = "#000000"
        else:
            ink = "#ffffff"
        axes.text(index + 0.5, 0.42, f"{index}", fontsize=8, fontweight="bold", color=ink, ha="center")
        axes.text(index + 0.5, 0.24, value, fontsize=8.5, color=theme["ink"], ha="center", va="center")
        axes.text(
            index + 0.5,
            0.09,
            f"L {lightness:.3f}   C {chroma:.3f}\nh {hue:.1f}°   ring {ring_of_color[index]}",
            fontsize=7,
            color=theme["muted"],
            ha="center",
            va="center",
            linespacing=1.5,
        )


def draw_delta_e(figure, axes, palette, theme):
    """The 66 pairwise distances, with the smallest ones painted loudest."""
    matrix = palette.delta_e_matrix
    size = matrix.shape[0]
    upper = np.triu(np.ones_like(matrix, dtype=bool), 1)
    shown = np.where(upper, matrix, np.nan)
    minimum, maximum = palette.min_delta_e, float(matrix.max())

    # The lower triangle is NaN, and "bad" is what paints it. It has to be the surface,
    # or the empty half reads as a value.
    ramp = LinearSegmentedColormap.from_list("delta_e", theme["delta_ramp"]).with_extremes(bad=theme["surface"])
    image = axes.imshow(shown, cmap=ramp, vmin=minimum, vmax=maximum, zorder=1)

    # Binding pairs sit exactly at vmin, so they always land on the ramp's first and
    # most saturated step. Their box and label go surface-colored, which reads on deep
    # red where near-black ink does not.
    binding = set(palette.binding_pairs)
    for row, column in binding:
        axes.add_patch(
            Rectangle((column - 0.5, row - 0.5), 1, 1, fill=False, edgecolor=theme["surface"], linewidth=1.6, zorder=7)
        )

    threshold = minimum + SATURATED_CELL_FRACTION * (maximum - minimum)
    for row in range(size):
        for column in range(row + 1, size):
            if (row, column) in binding:
                ink, weight = theme["surface"], "bold"
            elif matrix[row, column] < threshold:
                ink, weight = theme["surface"], "normal"
            else:
                ink, weight = theme["muted"], "normal"
            axes.text(
                column,
                row,
                f"{matrix[row, column]:.0f}",
                fontsize=6.2,
                fontweight=weight,
                ha="center",
                va="center",
                color=ink,
                zorder=6,
            )

    # A strip of the palette along each axis, so an index maps to a color without a legend.
    for index, value in enumerate(palette.hexes):
        axes.add_patch(Rectangle((index - 0.42, -1.42), 0.84, 0.84, facecolor=value, ec="none", clip_on=False))
        axes.add_patch(Rectangle((-1.42, index - 0.42), 0.84, 0.84, facecolor=value, ec="none", clip_on=False))

    axes.set_xticks(range(size))
    axes.set_yticks(range(size))
    axes.set_xticklabels(range(size), fontsize=7.5)
    axes.set_yticklabels(range(size), fontsize=7.5)
    axes.set_xlim(-1.6, size - 0.5)
    axes.set_ylim(size - 0.5, -1.6)
    if len(binding) == 1:
        row, column = next(iter(binding))
        headline = f"worst is {row}–{column} at {minimum:.2f}"
    else:
        headline = f"{len(binding)} boxed pairs all pinned at {minimum:.2f}"
    axes.set_title(f"CIEDE2000 between every pair  —  {headline}", fontsize=11, color=theme["ink"])
    style_axes(axes, theme)
    for spine in axes.spines.values():
        spine.set_visible(False)

    bar = figure.colorbar(image, ax=axes, fraction=0.045, pad=0.03)
    bar.outline.set_visible(False)
    bar.ax.tick_params(labelsize=7.5, colors=theme["muted"], length=0)
    bar.set_label("ΔE00   (red = too close)", fontsize=8.5, color=theme["muted"])


def style_axes(axes, theme):
    axes.set_facecolor(theme["surface"])
    axes.tick_params(colors=theme["muted"], labelsize=8, length=0)
    for spine in axes.spines.values():
        spine.set_color(theme["hairline"])
        spine.set_linewidth(0.8)


def build_figure(palette, theme=None):
    """Render one palette. Returns the matplotlib figure, which the caller closes."""
    if theme is None:
        theme = theme_for()
    figure = plt.figure(figsize=(15.0, 9.4), facecolor=theme["surface"])
    grid = figure.add_gridspec(2, 2, height_ratios=[1.0, 0.42], width_ratios=[1.0, 1.05], hspace=0.28, wspace=0.16)
    draw_wheel(figure.add_subplot(grid[0, 0]), palette, theme)
    draw_delta_e(figure, figure.add_subplot(grid[0, 1]), palette, theme)
    draw_swatches(figure.add_subplot(grid[1, :]), palette, theme)

    n_rings = palette.layout.n_rings
    n_chroma = palette.layout.n_chroma
    shared = ""
    if n_chroma == 1:
        shared = ", sharing one chroma"
    elif n_chroma < n_rings:
        shared = f", in {n_chroma} chroma groups"
    figure.suptitle(
        f"12 colors on {n_rings} Oklab {'ring' if n_rings == 1 else 'rings'}{shared}"
        f"  —  worst pair {palette.min_delta_e:.2f} ΔE00"
        f"  ({palette.min_delta_e_quantized:.2f} after 8-bit quantization)",
        fontsize=13,
        color=theme["ink"],
        x=0.5,
        y=0.985,
    )
    config = palette.config
    figure.text(
        0.5,
        0.955,
        f"maximin CIEDE2000 in {config.get('gamut', 'sRGB')}"
        f"  ·  {config.get('restarts', '?')} restarts × {config.get('evals_per_restart', '?')} evals"
        f"  ·  seed {config.get('seed', '?')}"
        f"  ·  generated {palette.generated[:10]}",
        fontsize=9,
        color=theme["muted"],
        ha="center",
    )
    figure.subplots_adjust(top=0.90, bottom=0.05, left=0.06, right=0.97)
    return figure


def save_figure(palette, path, dark=False, dpi=160):
    """Render and write a PNG. Returns the path."""
    theme = theme_for(dark)
    figure = build_figure(palette, theme)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=dpi, facecolor=theme["surface"])
    plt.close(figure)
    return path
