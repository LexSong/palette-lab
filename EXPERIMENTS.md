# Experiment details

Methodology, search results, and design notes behind the palettes shown in
[README.md](README.md).

A **ring** is a set of colors sharing one Oklab lightness `L` and one chroma `C`,
differing only in hue. That constraint is what makes the palette look deliberate. A
**layout** says how the 12 colors split across rings, written `6+6`, and whether the
rings share one chroma, written `6+6:C`.

"Hard to confuse" means CIEDE2000. The search maximizes the *smallest* distance over all
66 pairs, so the palette's worst confusion is as mild as it can be. Every color stays
inside sRGB.

## Run it

One script per experiment. Each writes its own JSON, and `--plot` adds the figure.

```sh
uv run scripts/experiment_6plus6.py --plot                  # ~12 s -> results/6+6.json
uv run scripts/experiment_5plus7.py --plot
uv run scripts/experiment_6plus6_shared_chroma.py --plot
uv run scripts/experiment_5plus7_shared_chroma.py --plot

for e in scripts/experiment_*.py; do uv run "$e" --plot; done   # all four, ~50 s

uv run scripts/visualize_palette.py results/6+6.json            # re-render one
uv run scripts/visualize_palette.py results/6+6-sharedC.json --dark

uv run scripts/render_readme_swatches.py     # regenerate images/*.png for README.md
```

## Results

| experiment | min ΔE00 | after 8-bit | rings |
|---|---|---|---|
| **6+6** | **25.12** | 24.76 | L=0.550 C=0.119, L=0.802 C=0.115 |
| **6+6:C** | 25.07 | **24.88** | L=0.548, L=0.797, both C=0.119 |
| 5+7 | 24.85 | 24.76 | L=0.497 C=0.096, L=0.719 C=0.153 |
| 5+7:C | 24.82 | 24.67 | L=0.515, L=0.738, both C=0.137 |

Pick `6+6` for the highest exact separation, `6+6:C` for the simpler palette that ships
better. Sharing one chroma costs 0.20% there, and it survives 8-bit quantization
*better*, 24.88 against 24.76.

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

## What was tried and dropped

One ring of 12 reaches 14.60. A single lightness leaves CIEDE2000 nothing to work with
but hue, so two rings beat one by 72%.

`4+8` reaches 21.80 and `3+9` reaches 19.45. Past `5+7` the split gets too uneven to pay.

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
- **The JSON** stores only what cannot be recomputed: the layout, 12 OKLCh triples, the
  settings, and the two headline numbers. About 2.3 KB. Hex, the ΔE matrix and the binding
  pairs are derived on load in roughly 1 ms, so a stored number can never drift from the
  palette it describes.
- **The color math** re-anchors Oklab's LMS matrix onto sRGB's own white. Without it,
  white lands at Oklab L=1.0003 and the gamut boundary moves by 0.1%, enough to change a
  hex digit. `color.py` says why at length.

Run `uv run pytest` for the checks. The color math is cross-checked against `coloraide`,
an independent implementation.
