"""Render the hue-sorted swatch strip PNGs that README.md embeds.

GitHub strips both `style` and `bgcolor` from HTML in rendered Markdown, so an inline
color table shows empty cells. A PNG is the reliable way to put color blocks in a
GitHub-rendered README.

Usage:
    uv run scripts/render_readme_swatches.py
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from palette_lab import palette as palette_module

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "images"

# (output stem, results file). README shows the shared-chroma layouts as the two main
# palettes, plus the independent-chroma 5+7 as a variation. The independent-chroma 6+6
# is left out: side by side with 6+6-sharedC it looks nearly identical, so it earns a
# place in EXPERIMENTS.md's numbers but not a second image here.
PALETTES = [
    ("6+6", "6+6-sharedC.json"),
    ("5+7", "5+7-sharedC.json"),
    ("5+7-alt", "5+7.json"),
]

SWATCH = 1.0
GAP = 0.12
MARGIN = 0.16
LABEL_HEIGHT = 0.34


def render(hexes, output_path):
    n = len(hexes)
    width = MARGIN * 2 + n * SWATCH + (n - 1) * GAP
    height = MARGIN * 2 + SWATCH + LABEL_HEIGHT

    figure = plt.figure(figsize=(width, height), dpi=200)
    axes = figure.add_axes((0.0, 0.0, 1.0, 1.0))
    axes.set_xlim(0, width)
    axes.set_ylim(0, height)
    axes.set_aspect("equal")
    axes.axis("off")
    figure.patch.set_facecolor("#ffffff")

    for index, hex_code in enumerate(hexes):
        x = MARGIN + index * (SWATCH + GAP)
        y = MARGIN + LABEL_HEIGHT
        axes.add_patch(Rectangle((x, y), SWATCH, SWATCH, facecolor=hex_code, edgecolor="none"))
        axes.text(
            x + SWATCH / 2,
            MARGIN + LABEL_HEIGHT / 2,
            hex_code,
            fontsize=11,
            family="monospace",
            color="#1c1e21",
            ha="center",
            va="center",
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, facecolor="#ffffff")
    plt.close(figure)
    print(f"wrote {output_path}")


def main():
    for stem, filename in PALETTES:
        loaded = palette_module.load(REPO_ROOT / "results" / filename)
        order = sorted(range(len(loaded.hexes)), key=lambda i: loaded.oklch[i, 2])
        hexes = [loaded.hexes[i] for i in order]
        render(hexes, OUTPUT_DIR / f"{stem}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
