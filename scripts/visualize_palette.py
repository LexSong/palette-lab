"""Render one experiment's JSON.

Usage:
    uv run scripts/visualize_palette.py results/6+6.json
    uv run scripts/visualize_palette.py results/6+6-sharedC.json --white-bg --no-show
"""

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt

from palette_lab import palette as palette_module
from palette_lab import plot


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", type=Path, help="JSON written by an experiment script")
    parser.add_argument("--white-bg", action="store_true", help="render on a white surface instead of dark")
    parser.add_argument("--save", type=Path, help="write the PNG here (default: beside the JSON)")
    parser.add_argument("--no-show", action="store_true", help="do not open a window")
    parser.add_argument("--dpi", type=int, default=160)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    palette = palette_module.load(args.path)

    if args.save:
        output = args.save
    else:
        suffix = "-white" if args.white_bg else ""
        output = args.path.with_name(f"{args.path.stem}{suffix}.png")

    theme = plot.theme_for(not args.white_bg)
    figure = plot.build_figure(palette, theme)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=args.dpi, facecolor=theme["surface"])
    print(f"wrote {output}")
    print(f"{palette.layout.name}: {' '.join(palette.hexes)}")

    if not args.no_show:
        plt.show()
    plt.close(figure)
    return 0


if __name__ == "__main__":
    sys.exit(main())
