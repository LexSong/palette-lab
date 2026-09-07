# Experiment details

Methodology, search results, and design notes behind the palettes shown in
[README.md](README.md).

A **ring** is a set of colors sharing one Oklab lightness `L` and one chroma `C`,
differing only in hue. That constraint is what makes the palette look deliberate. A
**layout** says how the 12 colors split across rings, written `6+6`, and which rings
share a chroma. Every ring sharing one is written `6+6:C`. Rings sharing in groups are
written as the slot each ring draws from, so `5+5+2` with `(0, 1, 1)` gives ring 0 its
own chroma and welds rings 1 and 2 to a second.

A layout may also set a **lightness floor** and a **lightness ceiling**, which close the
bottom and the top of the range the search may use. `5+5+2` sets a floor of 0.45.
`bright12` sets both, 0.60 and 0.85, and gives every color its own ring, so "ring" there
means one color rather than a group.

"Hard to confuse" means CIEDE2000. The search maximizes the *smallest* distance over all
66 pairs, so the palette's worst confusion is as mild as it can be. Every color stays
inside sRGB.

## Run it

One script per experiment. Each writes its own JSON, and `--plot` adds the figure.

```sh
uv run scripts/experiment_5plus5plus2.py --plot             # ~27 s -> results/5+5+2.json
uv run scripts/experiment_6plus6.py --plot                  # ~12 s -> results/6+6.json
uv run scripts/experiment_5plus7.py --plot
uv run scripts/experiment_6plus6_shared_chroma.py --plot
uv run scripts/experiment_5plus7_shared_chroma.py --plot
uv run scripts/experiment_bright12.py --restarts 40 --evals 5000 --plot   # ~5 min

for e in scripts/experiment_*.py; do uv run "$e" --plot; done   # all six

uv run scripts/visualize_palette.py results/6+6.json            # re-render one
uv run scripts/visualize_palette.py results/6+6-sharedC.json --dark

uv run scripts/render_readme_swatches.py     # regenerate images/*.png for README.md
```

## Results

| experiment | min ΔE00 | after 8-bit | rings |
|---|---|---|---|
| **5+5+2** | **28.17** | **28.06** | L=0.488 C=0.100, L=0.741 C=0.156, L=0.903 C=0.156 |
| 6+6 | 25.12 | 24.76 | L=0.550 C=0.119, L=0.802 C=0.115 |
| 6+6:C | 25.07 | 24.88 | L=0.548, L=0.797, both C=0.119 |
| 5+7 | 24.85 | 24.76 | L=0.497 C=0.096, L=0.719 C=0.153 |
| 5+7:C | 24.82 | 24.67 | L=0.515, L=0.738, both C=0.137 |
| bright12 | 24.13 | 23.82 | 12 rings in L=0.600..0.850, all C=0.135 |

`bright12` needs `--restarts 40 --evals 5000` to reach that. It carries 25 free parameters
against 15 to 17 for the ringed layouts, and the defaults leave it short.

`5+5+2` wins by 12.1% over `6+6`, and its third lightness is where that comes from.
Among the two-lightness layouts, pick `6+6` for the highest exact separation and
`6+6:C` for the simpler palette that ships better. Sharing one chroma costs 0.20%
there, and it survives 8-bit quantization *better*, 24.88 against 24.76.

`5+5+2`:

`#904839` `#705f00` `#007153` `#00688f` `#724e8a`
`#f58d3d` `#6dc364` `#16b8ff` `#b993ff` `#fc7d92`
`#ffde54` `#00fff7`

**Sharing costs less on the uneven split, which is the opposite of what it looks like.**
Left free, `5+7` gives its rings 0.096 and 0.153, so one shared value has to move both a
long way, against 0.004 apart on `6+6`. Yet `5+7:C` gives up 0.10% and `6+6:C` gives up
0.20%. The reason is that the 5-ring's chroma was never the binding constraint, so
raising it to 0.137 cost nothing and paid for what the 7-ring lost. At 8 bits the
ordering flips back: `5+7:C` loses 0.08 to `5+7`, where `6+6:C` gains 0.12 over `6+6`.

`6+6`:

`#ab515f` `#a55d1d` `#787600` `#00875d` `#007bae` `#7a61ae`
`#ff9faa` `#f4ad6f` `#bfc66c` `#5ed7bd` `#68ccfb` `#c7aeff`

`6+6:C`:

`#ab505e` `#a45c1d` `#777600` `#00865c` `#007aad` `#7a60ad`
`#ff9ca9` `#f5aa6b` `#bac669` `#56d6bc` `#61cbfb` `#c7acff`

`bright12`:

`#c25a6f` `#ff9676` `#b66c00` `#fdc35e` `#828900` `#bcdd76`
`#009865` `#4feacf` `#41d1ff` `#3584cd` `#946dc5` `#ff9fdb`

## Why 5+5+2 groups its chroma, and why it needs a floor

Give the optimizer a freedom and it spends part of it going gray, because a low chroma at
an extreme lightness sits far from everything else and costs the objective nothing. The
smallest chroma in the palette tracks how much freedom it was given:

| layout | constraints | min ΔE00 | smallest C in the palette |
|---|---|---|---|
| 6+6:C | one chroma for all twelve | 25.07 | 0.119 |
| 5+5+2, free chroma | none | 29.35 | 0.068 |
| 5+5+2, free chroma | L >= 0.40 | 28.14 | 0.041 |
| 12 free colors | L >= 0.40 | 34.60 | 0.008 |

The last row is a palette with `#fff9fc` in it, a white with a rumour of pink, and
`#404d34`, a dark olive-gray pressed against the floor. Both score well and neither is a
chart color. `6+6:C`'s real protection was never the ring: one shared chroma forced all
twelve to stay colorful.

`bright12` is the same twelve free colors as that last row and has none of the problem,
because one shared chroma leaves no color free to go gray alone. It gives up separation
for it — 24.13 against 34.60 — and every color it keeps is one you would put on a chart.

**A lightness floor alone relocates the escape rather than closing it.** Free, `5+5+2`
sends its two-color ring to L=0.206. Floored at 0.40 it sends the same ring to L=0.925 and
C=0.041, pale instead of dark, for the same reason.

**Grouping the chroma closes it.** Welding the two-color ring to the five vivid colors
means going pale would drag five colors with it, so there is no gray corner left to reach.
That is why `5+5+2` needs no chroma floor: its smallest chroma lands at 0.100 on its own.

The lightness floor stays, as a guard rather than a bound. It never binds — the rings
settle at 0.488, 0.741 and 0.903, all clear of 0.45 — but removing it lets the search
prefer a different basin that scores 28.49 with the two-color ring at L=0.280, on colors
too dark to ship. The floor excludes that basin without touching the one we want.

**Pinning the dark ring instead of flooring it does not work.** Fix ring 0 at L=0.5 and
the palette scores 28.00, 0.6% below flooring. Fix it at 0.6 and a *free* ring takes over
the dark job at L=0.338. Requiring every color above 0.6 costs the whole gain: 24.94,
below `6+6`.

## Why bright12 has a ceiling, and what the band costs

`bright12` is the only layout here built for a dark surface rather than a page. It gives
each of the twelve colors its own lightness, welds all twelve to one chroma, and holds
every one inside `0.60 <= L <= 0.85`.

The ceiling is the part worth explaining. A floor alone constrains one end, and the
search spends the other: given only `L >= 0.60` it puts a color at L=0.961. That buys
separation a dimmed screen cannot show, and it is invisible on white. Closing the top is
nearly free.

| twelve free colors, one chroma | min ΔE00 | C | L range | worst on white |
|---|---|---|---|---|
| L >= 0.45 | 28.90 | 0.123 | 0.450..0.977 | 1.05:1 |
| L >= 0.55 | 26.32 | 0.116 | 0.550..0.928 | 1.19:1 |
| L >= 0.60 | 24.65 | 0.137 | 0.600..0.961 | 1.09:1 |
| L in [0.60, 0.90] | 24.53 | 0.139 | 0.600..0.900 | 1.28:1 |
| **L in [0.60, 0.85]** | **24.13** | **0.135** | 0.600..0.850 | 1.50:1 |

Dropping the ceiling from 0.90 to 0.85 costs 1.6% and is what keeps the palette off the
top of the range.

The point of the band is what happens when the display dims. Scaling linear output by a
backlight factor, with the viewer's white point left at ambient, gives:

| backlight | 100% | 50% | 25% | 10% |
|---|---|---|---|---|
| bright12 | 24.1 | 20.0 | **15.8** | **10.6** |
| 5+5+2 | **28.2** | **21.5** | 15.1 | 10.2 |
| 6+6:C | 25.1 | 21.3 | 14.4 | 9.2 |
| 5+7:C | 24.8 | 20.2 | 14.5 | 8.5 |

`bright12` starts last and finishes first. `5+7:C` falls furthest because its darkest
color sits at L=0.515 and crushes toward black; `bright12` has nothing below 0.600.

Do not measure this by compressing Oklab lightness toward the palette's own mean. That
converges every color on mid-grey, which flatters a palette whose binding pairs share a
lightness and hides the cost of being dark — it ranks `5+7:C` first, the reverse of the
result above.

## Why one chroma costs less at twelve rings than at three

A ring's shared chroma is capped by the worst hue anywhere on that ring, so the fewer
colors per ring, the higher the ceiling. Forcing one chroma onto three rings is expensive;
onto twelve one-color rings it is not.

| layout | rings | one chroma | its C |
|---|---|---|---|
| 5+5+2 | 3 | 26.30 | 0.096 |
| 4+4+4 | 3 | 26.20 | 0.101 |
| 4+3+3+2 | 4 | 27.50 | 0.137 |
| 4+6+1+1 | 4 | 27.68 | 0.142 |
| bright12 | 12 | 24.13 | 0.135 |

This is why `bright12` can be uniform in saturation without looking washed out, and why
`5+5+2` needs two chroma groups to avoid exactly that.

## What was tried and dropped

One ring of 12 reaches 14.60. A single lightness leaves CIEDE2000 nothing to work with
but hue, so two rings beat one by 72%.

`4+8` reaches 21.80 and `3+9` reaches 19.45. Past `5+7` the split gets too uneven to pay.

Moving a color out of `5+5+2`'s dark ring loses either way: `4+5+3` reaches 27.73 and
`4+6+2` reaches 26.78, against 28.17. Five is the right size for the dark ring, and it is
the only one of these whose floor stays inactive — every layout with four or fewer dark
colors settles hard against `L >= 0.45` and wants to go lower.

Equal thirds are worse still. `4+4+4` reaches 27.63 with grouped chroma, because the
brightest ring's size sets how bright it can be: one color reaches L=0.977, two reach
0.903, four only 0.851. Near white the gamut narrows, so four colors up there cannot
spread on hue and the search refuses to go.

Giving the light end solo rings works for the same reason. `4+6+1+1` puts cyan alone at
L=0.886 and a pale yellow-green alone at 0.943 — the two hues whose chroma peaks highest
in sRGB — and reaches the highest shared chroma of any one-chroma layout tried, 0.142.

## Why the two rings land on the same hues

The `6+6` rings are not offset. Their hues match within 4°, which looks like a bug and is
not. Optimize each ring completely alone, knowing nothing about the other, and it picks
nearly the same hues it has in the joint solution:

| | ring optimized alone | same ring in the joint 6+6 |
|---|---|---|
| L=0.550 | 12.1, 56.3, 111.2, 163.8, 238.3, 298.9 | 12.1, 57.0, 108.9, 162.8, 236.5, 297.8 |
| L=0.802 | 12.2, 61.6, 115.9, 180.3, 235.8, 297.4 | 12.2, 60.9, 112.8, 176.7, 231.4, 298.2 |

Both rings face the same sRGB gamut shape, which pinches near yellow-green and bulges
near blue, and the same CIEDE2000 hue non-uniformity. So both independently reach the
same answer. The alignment is a consequence, not coordination.

Offsetting would pay only if the cross-ring pairs were the binding constraint. They are
not. A lightness gap of 0.252 buys ΔE00 ≈ 25.1 on its own, the same as a 45-75° hue step,
so within-ring and cross-ring pairs bind at the same value at once. That is what a
converged maximin looks like, and there is no slack left to trade by rotating.

Offsetting *does* win when hue spacing is forced even. Holding both rings at 60° steps
and optimizing only the two lightnesses:

| ring-1 offset | 0° | 10° | 20° | 30° | 40° | 50° |
|---|---|---|---|---|---|---|
| min ΔE00 | 19.45 | 19.63 | 19.75 | **20.19** | 19.82 | 19.64 |

Interleaving is worth 3.8% there. Free hues are worth far more: 25.12 against 20.19. So
the optimizer spends its freedom on uneven spacing rather than on offset. Gaps in the
winner run 45-74° on one ring and 49-75° on the other, against 60° even.

Four independent seeds at 240k evaluations each all land on 25.1243, so that is global.

## Layout

```
src/palette_lab/
  color.py       OKLCh <-> sRGB <-> CIE Lab and CIEDE2000, vectorized
  search.py      the encoding and objective, plus CMA-ES with restarts
  polish.py      SLSQP on the epigraph form
  palette.py     the Palette record, and the JSON
  plot.py        the figure
  experiment.py  the pipeline the experiment scripts share
scripts/
  experiment_*.py        one per experiment, a docstring and a Layout
  visualize_palette.py   render any one JSON
```

- **The encoding** makes hues a phase plus softmax gaps summing to 360°, which removes
  the permutation symmetry. Chroma is a fraction of the worst-hue limit for its slot, so
  every candidate is in gamut by construction and the search needs no penalty term. A
  whole CMA-ES population is scored in one batched call.
- **The polish** solves `maximize t` subject to `ΔE00 ≥ t`, which is smooth where the raw
  `min` is not. Worth about 2%. Then a second stage freezes `t` and maximizes the mean.
  Without it the palette is underdetermined: a color in no binding pair never enters the
  active constraints, so the objective is flat in its direction and SLSQP stops wherever
  its iteration lands. `6+6:C` has one such color and `5+7` has five. The stages are
  lexicographic rather than a weighted sum, because `min + w * mean` would sell real
  minimum for mean, and the minimum is the number we rank on.
- **Choosing between refined candidates** ranks on the minimum, then on the mean. They
  tie on the minimum often — 11 of 13 on `6+6` — and ranking on the minimum alone hands
  the win to whichever tied candidate came first. That is worth 0.27 of mean ΔE00 on
  `5+7:C`, where two candidates reach the same worst pair at means of 43.62 and 43.89.
- **The restarts** each contribute one candidate, their own best, not their best few. A
  restart improves monotonically, so its late generations fill the top of any global
  ranking and crowd every other restart out, and then we refine one solution three
  times. One per restart costs nothing on the four layouts here, because 15-16
  parameters converge either way. It matters at higher dimension: on a 36-parameter
  layout a global top-3 reached 35.21, where one per restart reached 36.20.
- **The equal-spacing baseline** enumerates one lightness per ring off a shared grid, so
  its size is more than exponential in the ring count: 4753 candidates at two rings on a
  97-point grid, 157k at three, 3.9M at four. The grid coarsens until the enumeration fits
  in 200k candidates, which leaves two and three rings on the full 97 points and gives
  `bright12` nine. A coarser baseline is a weaker floor but still a real one, and the
  search has to clear it either way.
- **The figure** plots hue against lightness, not the Oklab a/b plane. Those are the two
  axes a reader separates colors by, and the pair a dimmed screen attacks, so a palette
  built for dark backgrounds has to show both. The a/b wheel dropped lightness entirely.
  Every panel numbers the colors in hue order; the stored order groups them by ring,
  because `ring_of_color` and `verify` depend on that, so the reordering is in the view
  only.
- **The JSON** stores only what cannot be recomputed: the layout, 12 OKLCh triples, the
  settings, and the two headline numbers. About 2.3 KB. Hex, the ΔE matrix and the binding
  pairs are derived on load in roughly 1 ms, so a stored number can never drift from the
  palette it describes.
- **The color math** re-anchors Oklab's LMS matrix onto sRGB's own white. Without it,
  white lands at Oklab L=1.0003 and the gamut boundary moves by 0.1%, enough to change a
  hex digit. `color.py` says why at length.

Run `uv run pytest` for the checks. The color math is cross-checked against `coloraide`,
an independent implementation.
