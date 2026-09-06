"""The pipeline every experiment script runs: search, polish, verify, save.

Each script under `scripts/` is a declaration of one layout. This holds the logic, so a
new experiment costs a docstring and a Layout, with nothing duplicated.
"""

import argparse
from pathlib import Path

import numpy as np

from palette_lab import color
from palette_lab import palette as palette_module
from palette_lab import plot
from palette_lab.polish import polish
from palette_lab.search import search_layout

DEFAULT_OUTPUT_DIR = Path("results")


def parse_args(argv=None, description=None):
    parser = argparse.ArgumentParser(description=description, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--restarts", type=int, default=12, help="CMA-ES restarts (default: 12)")
    parser.add_argument("--evals", type=int, default=4000, help="evaluations per restart (default: 4000)")
    parser.add_argument("--polish-top", type=int, default=3, help="CMA-ES solutions to refine (default: 3)")
    parser.add_argument("--seed", type=int, default=0, help="base seed (default: 0)")
    parser.add_argument(
        "--out-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help=f"where the JSON goes (default: {DEFAULT_OUTPUT_DIR})"
    )
    parser.add_argument("--plot", action="store_true", help="also write a PNG beside the JSON")
    parser.add_argument("--dark", action="store_true", help="render that PNG on a dark surface")
    parser.add_argument("--quiet", action="store_true", help="only print the summary line")
    return parser.parse_args(argv)


def verify(oklch, layout, baseline):
    """Re-derive the guarantees from scratch. A bad palette must not reach the JSON."""
    linear = color.oklab_to_linear_srgb(color.oklch_to_oklab(oklch))
    excess = color.gamut_excess(linear)
    if excess.max() > 0.0:
        raise AssertionError(f"{layout.name}: out of sRGB by {excess.max():.3e}")

    for ring in range(layout.n_rings):
        members = layout.ring_of_color == ring
        for channel, name in ((0, "lightness"), (1, "chroma")):
            spread = np.ptp(oklch[members, channel])
            if spread > 1e-9:
                raise AssertionError(f"{layout.name}: ring {ring} {name} varies by {spread:.3e}, so it is not a ring")

    if layout.shared_chroma:
        spread = np.ptp(oklch[:, 1])
        if spread > 1e-9:
            raise AssertionError(f"{layout.name}: chroma varies by {spread:.3e} but the rings are meant to share it")

    minimum = float(color.pairwise_delta_e(color.linear_srgb_to_lab(linear)).min())
    if minimum < baseline - 1e-9:
        raise AssertionError(f"{layout.name}: {minimum:.4f} lost to the equal-spacing baseline {baseline:.4f}")
    return minimum


def run(layout, restarts=12, evals=4000, polish_top=3, seed=0, verbose=False):
    """Search, refine and check one layout. Returns a Palette."""
    candidates, baseline = search_layout(layout, restarts=restarts, max_evaluations=evals, seed=seed, verbose=verbose)

    best_oklch, best_minimum = None, -np.inf
    for params in candidates[:polish_top]:
        oklch, minimum = polish(params, layout)
        if minimum > best_minimum:
            best_oklch, best_minimum = oklch, minimum
    if best_oklch is None:
        raise ValueError(f"polish_top={polish_top} refined nothing, so there is no palette to check")

    verify(best_oklch, layout, baseline)
    return palette_module.Palette(
        layout=layout,
        oklch=best_oklch,
        config={
            "gamut": "sRGB",
            "objective": "maximin_ciede2000",
            "restarts": restarts,
            "evals_per_restart": evals,
            "polish_top": polish_top,
            "seed": seed,
        },
    )


def main(layout, argv=None, description=None):
    args = parse_args(argv, description)
    if not args.quiet:
        print(f"{layout.name}: {layout.n_params} parameters, {args.restarts} restarts x {args.evals} evals")

    palette = run(
        layout,
        restarts=args.restarts,
        evals=args.evals,
        polish_top=args.polish_top,
        seed=args.seed,
        verbose=not args.quiet,
    )

    json_path = args.out_dir / f"{layout.slug}.json"
    palette_module.save(palette, json_path)
    print(
        f"{layout.name:>6}  min dE00 {palette.min_delta_e:7.3f}"
        f"  ({palette.min_delta_e_quantized:7.3f} at 8-bit)"
        f"  rings {'  '.join(f'L={value:.3f} C={chroma:.3f}' for value, chroma in palette.rings)}"
    )
    print(f"  {' '.join(palette.hexes)}")
    print(f"  wrote {json_path}")

    if args.plot:
        suffix = ""
        if args.dark:
            suffix = "-dark"
        png_path = plot.save_figure(palette, args.out_dir / f"{layout.slug}{suffix}.png", dark=args.dark)
        print(f"  wrote {png_path}")
    return 0
