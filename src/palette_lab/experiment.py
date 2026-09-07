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
from palette_lab.polish import MINIMUM_TOLERANCE
from palette_lab.polish import polish
from palette_lab.search import search_layout

DEFAULT_OUTPUT_DIR = Path("results")

# Past this many rings the summary line prints a lightness span instead of every ring.
MAX_RINGS_LISTED = 4


def parse_args(argv=None, description=None):
    parser = argparse.ArgumentParser(description=description, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--restarts", type=int, default=12, help="CMA-ES restarts (default: 12)")
    parser.add_argument("--evals", type=int, default=4000, help="evaluations per restart (default: 4000)")
    parser.add_argument(
        "--polish-top", type=int, default=None, help="CMA-ES solutions to refine (default: every restart)"
    )
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

    chroma_of_color = layout.chroma_of_color
    for slot in range(layout.n_chroma):
        spread = np.ptp(oklch[chroma_of_color == slot, 1])
        if spread > 1e-9:
            raise AssertionError(
                f"{layout.name}: chroma varies by {spread:.3e} across slot {slot} but its rings are meant to share it"
            )

    floor, ceiling = layout.lightness_range
    darkest, lightest = float(oklch[:, 0].min()), float(oklch[:, 0].max())
    if darkest < floor - 1e-9:
        raise AssertionError(f"{layout.name}: lightness {darkest:.4f} is under the layout floor {floor}")
    if lightest > ceiling + 1e-9:
        raise AssertionError(f"{layout.name}: lightness {lightest:.4f} is over the layout ceiling {ceiling}")

    minimum = float(color.pairwise_delta_e(color.linear_srgb_to_lab(linear)).min())
    if minimum < baseline - 1e-9:
        raise AssertionError(f"{layout.name}: {minimum:.4f} lost to the equal-spacing baseline {baseline:.4f}")
    return minimum


def run(layout, restarts=12, evals=4000, polish_top=None, seed=0, verbose=False):
    """Search, refine and check one layout. Returns a Palette.

    `polish_top` of None refines every candidate `search_layout` returns, which is one per
    restart plus the baseline. Refining them all is what makes the restarts worth running:
    the CMA-ES score does not say how far SLSQP will carry a candidate, so the best
    refined palette often comes from a restart that did not rank first.
    """
    candidates, baseline = search_layout(layout, restarts=restarts, max_evaluations=evals, seed=seed, verbose=verbose)

    refined = []
    for params in candidates[:polish_top]:
        oklch, minimum = polish(params, layout)
        pairs = color.pairwise_delta_e(color.oklab_to_lab(color.oklch_to_oklab(oklch)))
        refined.append((minimum, float(pairs.mean()), oklch))
    if not refined:
        raise ValueError(f"polish_top={polish_top} refined nothing, so there is no palette to check")

    # Candidates converge on the same worst pair, so ranking on the minimum alone leaves
    # ties, and the first one then wins by accident. Break them on the mean, which is the
    # order both polish stages already use.
    best_minimum = max(minimum for minimum, _, _ in refined)
    tied = [entry for entry in refined if entry[0] >= best_minimum - MINIMUM_TOLERANCE]
    best_oklch = max(tied, key=lambda entry: entry[1])[2]

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
    # One ring per color would print twelve of these, so past a handful give the span instead.
    if layout.n_rings <= MAX_RINGS_LISTED:
        rings = "  ".join(f"L={value:.3f} C={chroma:.3f}" for value, chroma in palette.rings)
    else:
        lightness, chroma = palette.oklch[:, 0], palette.oklch[:, 1]
        rings = f"{layout.n_rings} rings, L={lightness.min():.3f}..{lightness.max():.3f} C={chroma.min():.3f}"
    print(
        f"{layout.name:>6}  min dE00 {palette.min_delta_e:7.3f}"
        f"  ({palette.min_delta_e_quantized:7.3f} at 8-bit)  rings {rings}"
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
