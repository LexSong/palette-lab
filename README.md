# Twelve Colors, No Confusion

Twelve-color palettes for charts, maps, and dashboards. Most categorical
palettes blur together well before hitting twelve categories, so each of
these was searched by directly maximizing CIEDE2000 instead — the metric
closest to how people actually judge color similarity. Every color stays
inside sRGB, so it renders the same on any screen.

Each palette splits its twelve colors across two Oklab rings — a ring being
one fixed lightness and chroma, varying only in hue — and holds both rings to
the same chroma. Sharing chroma is what keeps a palette reading as one
deliberate set instead of a grab bag of colors from two different families.

Colors within each palette are sorted by hue below, not by which ring they
came from, so the two rows compare at a glance.

## The palettes

### 6+6 — the more separated of the two

![6+6](images/6+6.png)

### 5+7 — the more vivid of the two

![5+7](images/5+7.png)

`6+6` splits its twelve colors evenly and holds the largest worst-pair
distance of any layout tried. `5+7` splits them unevenly, five and seven,
which frees up room for a higher shared chroma — its colors sit more
saturated, at a small cost to that worst-pair distance.

### Variation: 5+7 without the shared chroma

![5+7, one chroma per ring](images/5+7-alt.png)

Let the two rings pick their own chroma instead of sharing one, and the
5-color ring settles lower while the 7-color ring climbs higher — muted next
to vivid, rather than uniform. It scores slightly higher than the shared
version above once every color is rounded to 8-bit hex, at the cost of the
two rings looking like they belong to different palettes.

## Why these work

- **The worst pair is what was optimized, not the average.** The search
  maximizes the *smallest* CIEDE2000 distance over all 66 pairs in the
  palette — not the average pair, the closest one. Nothing in a palette is
  more confusable than that.
- **Every color stays in sRGB.** No color needs a wide-gamut display or gets
  clipped and dulled on a normal one.

The exact scores, the ΔE00 matrices, and the other layouts tried and dropped
— including a plain `6+6` where each ring keeps its own chroma — are in
[EXPERIMENTS.md](EXPERIMENTS.md).

## Use a palette

Each palette's full data — hue and chroma per color, which ring it's on, the
CIEDE2000 matrix — is in `results/*.json` and loads with `palette_lab.palette.load`:

```sh
uv run scripts/visualize_palette.py results/6+6-sharedC.json
```

To regenerate everything from scratch, see [EXPERIMENTS.md](EXPERIMENTS.md#run-it).
