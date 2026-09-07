"""The figure: the a/b wheel, the CIEDE2000 matrix, and a swatch strip.

Everything here reads a `Palette` and derives what it needs. Both the experiment scripts
and `scripts/visualize_palette.py` call `build_figure`.
"""

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

# Every color gets the same circle. The a/b view needed a marker per ring because it
# dropped lightness; plotting lightness directly puts each ring on its own row, so shape
# would only repeat what position already says.
MARKER = "o"
# Fixed axes and a fixed marker scale, so two palettes can be compared by laying their
# figures side by side. Fitting either to the palette in hand would make a narrow band
# look wide and a muted palette look saturated.
LIGHTNESS_AXIS = (0.0, 1.0)
LIGHTNESS_TICKS = np.arange(0.0, 1.01, 0.1)
# The widest chroma sRGB reaches in Oklab, near magenta at L=0.70. `color.CHROMA_CEILING`
# is a search bound at 0.45 and would leave every real marker small.
WIDEST_SRGB_CHROMA = 0.32
MARKER_AREA = (70, 430)
# Past this many rings the legend names the palette as a whole. One line per ring would
# be twelve lines saying "1 colors", each listing the eleven rings it shares a chroma with.
MAX_RINGS_IN_LEGEND = 4

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


def theme_for(dark=True):
    if dark:
        return THEMES["dark"]
    return THEMES["light"]


def hue_order(palette):
    """Display order for a palette: round the hue circle, starting from red.

    The stored order groups colors by ring, because `ring_of_color` and `verify` both
    depend on that grouping, so this reorders the view and never the data. Every panel
    takes the same order, so the number on a swatch is the number on the matrix and on
    the wheel.
    """
    return np.argsort(palette.oklch[:, 2] % 360.0)


def draw_hue_lightness(axes, palette, theme, order=None):
    """Hue across, Oklab lightness up, chroma as marker size.

    These are the two axes a reader actually separates colors by, and the pair a dimmed
    screen attacks: dimming compresses lightness and leaves hue alone, so two colors close
    on both axes are the ones that will merge. An a/b wheel hides lightness entirely, which
    is the one thing a palette built for dark backgrounds has to show.
    """
    if order is None:
        order = hue_order(palette)
    oklch = palette.oklch
    hexes = palette.hexes
    lightness, chroma = oklch[:, 0], oklch[:, 1]

    axes.set_ylim(*LIGHTNESS_AXIS)
    axes.set_yticks(LIGHTNESS_TICKS)
    axes.set_xlim(-10, 370)
    axes.set_xticks(range(0, 361, 60))

    for value in LIGHTNESS_TICKS:
        axes.axhline(value, color=theme["hairline"], lw=0.6, zorder=0)
    for degrees in HUE_SPOKES:
        axes.axvline(degrees, color=theme["hairline"], lw=0.6, zorder=0)

    # A floor or ceiling the layout sets is drawn, so a palette pressed against one is
    # visibly pressed rather than merely low.
    for value, name in ((palette.layout.lightness_floor, "floor"), (palette.layout.lightness_ceiling, "ceiling")):
        if value is None:
            continue
        axes.axhline(value, color=theme["rule"], lw=1.0, ls="--", zorder=1)
        axes.annotate(
            f"{name} L={value:.2f}",
            (368, value),
            textcoords="offset points",
            xytext=(0, 4),
            fontsize=7.5,
            ha="right",
            color=theme["muted"],
            zorder=3,
        )

    low_area, high_area = MARKER_AREA
    for position, index in enumerate(order):
        index = int(index)
        axes.scatter(
            oklch[index, 2] % 360.0,
            lightness[index],
            s=low_area + (high_area - low_area) * min(chroma[index] / WIDEST_SRGB_CHROMA, 1.0),
            marker=MARKER,
            c=hexes[index],
            edgecolors=theme["surface"],
            linewidths=2.0,
            zorder=5,
        )
        axes.annotate(
            str(position),
            (oklch[index, 2] % 360.0, lightness[index]),
            textcoords="offset points",
            xytext=(0, -16),
            fontsize=8,
            fontweight="bold",
            ha="center",
            color=theme["ink"],
            zorder=6,
        )

    rings = palette.rings
    groups = palette.layout.groups

    def shared_with(ring):
        """Which other rings draw this ring's chroma from the same slot."""
        others = [other for other in range(len(groups)) if other != ring and groups[other] == groups[ring]]
        if not others:
            return ""
        return f" (shared with {', '.join(str(other) for other in others)})"

    if palette.layout.n_rings <= MAX_RINGS_IN_LEGEND:
        labels = [
            f"ring {ring}: {size} colors, L={value:.3f}, C={ring_chroma:.3f}{shared_with(ring)}"
            for ring, (size, (value, ring_chroma)) in enumerate(zip(palette.layout.sizes, rings, strict=True))
        ]
    else:
        span = f"L={lightness.min():.3f}..{lightness.max():.3f}"
        if np.ptp(chroma) < 1e-9:
            labels = [f"{palette.layout.n_rings} rings, one color each, {span}, C={chroma[0]:.3f}"]
        else:
            labels = [
                f"{palette.layout.n_rings} rings, one color each, {span}, C={chroma.min():.3f}..{chroma.max():.3f}"
            ]

    handles = [
        Line2D(
            [],
            [],
            marker=MARKER,
            linestyle="none",
            markersize=9,
            markerfacecolor=theme["muted"],
            markeredgecolor=theme["surface"],
            label=label,
        )
        for position, label in enumerate(labels)
    ]
    axes.legend(handles=handles, loc="lower left", fontsize=8, frameon=False, labelcolor=theme["ink"]).set_zorder(10)

    axes.set_xlabel("hue (degrees)", fontsize=9, color=theme["muted"])
    axes.set_ylabel("Oklab lightness", fontsize=9, color=theme["muted"])
    axes.set_title(f"Hue against lightness, sized by chroma  —  {palette.layout.name}", fontsize=11, color=theme["ink"])
    style_axes(axes, theme)


def draw_swatches(axes, palette, theme, order=None):
    """The palette in hue order, with black and white samples over each for a legibility read."""
    if order is None:
        order = hue_order(palette)
    hexes = palette.hexes
    ring_of_color = palette.layout.ring_of_color
    axes.set_xlim(0, len(hexes))
    axes.set_ylim(0, 1)
    axes.axis("off")
    axes.set_title("Swatches, in hue order", fontsize=11, color=theme["ink"], loc="left", pad=8)

    for position, index in enumerate(order):
        index = int(index)
        value = hexes[index]
        axes.add_patch(Rectangle((position + 0.02, 0.34), 0.96, 0.66, facecolor=value, edgecolor="none"))
        axes.text(position + 0.5, 0.86, "Aa", fontsize=11, color="#000000", ha="center", va="center")
        axes.text(position + 0.5, 0.60, "Aa", fontsize=11, color="#ffffff", ha="center", va="center")
        # The index has to stay readable on every swatch, so it takes whichever of black
        # or white the swatch's own lightness calls for. The "Aa" pair above is the
        # legibility test; this label is not part of it.
        lightness, chroma, hue = palette.oklch[index]
        if lightness > 0.62:
            ink = "#000000"
        else:
            ink = "#ffffff"
        axes.text(position + 0.5, 0.42, f"{position}", fontsize=8, fontweight="bold", color=ink, ha="center")
        axes.text(position + 0.5, 0.24, value, fontsize=8.5, color=theme["ink"], ha="center", va="center")
        axes.text(
            position + 0.5,
            0.09,
            f"L {lightness:.3f}   C {chroma:.3f}\nh {hue % 360.0:.1f}°   ring {ring_of_color[index]}",
            fontsize=7,
            color=theme["muted"],
            ha="center",
            va="center",
            linespacing=1.5,
        )


def draw_delta_e(figure, axes, palette, theme, order=None):
    """The 66 pairwise distances, with the smallest ones painted loudest.

    Rows and columns follow the same hue order as the swatches, so a number here names
    the same color there.
    """
    if order is None:
        order = hue_order(palette)
    order = np.asarray(order)
    matrix = palette.delta_e_matrix[np.ix_(order, order)]
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
    # `binding_pairs` names stored indices, so map them onto display positions and put
    # each pair back in upper-triangle order, which reordering can flip.
    position_of = {int(index): position for position, index in enumerate(order)}
    binding = set()
    for row, column in palette.binding_pairs:
        a, b = position_of[int(row)], position_of[int(column)]
        binding.add((min(a, b), max(a, b)))
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
    for index, value in enumerate([palette.hexes[int(i)] for i in order]):
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
    # One order, computed once, so the wheel, the matrix and the swatches agree on which
    # color each number names.
    order = hue_order(palette)
    draw_hue_lightness(figure.add_subplot(grid[0, 0]), palette, theme, order)
    draw_delta_e(figure, figure.add_subplot(grid[0, 1]), palette, theme, order)
    draw_swatches(figure.add_subplot(grid[1, :]), palette, theme, order)

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


def save_figure(palette, path, dark=True, dpi=160):
    """Render and write a PNG. Returns the path."""
    theme = theme_for(dark)
    figure = build_figure(palette, theme)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=dpi, facecolor=theme["surface"])
    plt.close(figure)
    return path
