# palette-lab

Finds 12 colors that are as hard to confuse as possible, arranged on rings in OKLab.

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
uv run scripts/experiment_6plus6.py --plot                  # ~11 s -> results/6+6.json
uv run scripts/experiment_5plus7.py --plot
uv run scripts/experiment_6plus6_shared_chroma.py --plot

for e in scripts/experiment_*.py; do uv run "$e" --plot; done   # all three, ~32 s

uv run scripts/visualize_palette.py results/6+6.json            # re-render one
uv run scripts/visualize_palette.py results/6+6-sharedC.json --dark
```

## Results

| experiment | min ΔE00 | after 8-bit | rings |
|---|---|---|---|
| **6+6** | **25.12** | 24.76 | L=0.550 C=0.119, L=0.802 C=0.115 |
| **6+6:C** | 25.07 | **24.88** | L=0.548, L=0.797, both C=0.119 |
| 5+7 | 24.85 | 24.76 | L=0.497 C=0.096, L=0.719 C=0.153 |

Pick `6+6` for the highest exact separation, `6+6:C` for the simpler palette that ships
better. Sharing one chroma costs 0.20%, and it survives 8-bit quantization *better*,
24.88 against 24.76.

`6+6`:

`#ab515f` `#a55d1d` `#787600` `#00875d` `#007bae` `#7a61ae`
`#ff9faa` `#f4ad6f` `#bfc66c` `#5ed7bd` `#68ccfb` `#c7aeff`

`6+6:C`:

`#ff9ca9` `#f5aa6b` `#bdc567` `#56d6bc` `#61cbfb` `#c7acff`
`#ab505e` `#a45c1d` `#777600` `#00865c` `#007aad` `#7a60ad`

## What was tried and dropped

One ring of 12 reaches 14.60. A single lightness leaves CIEDE2000 nothing to work with
but hue, so two rings beat one by 72%.

`4+8` reaches 21.80 and `3+9` reaches 19.45. Past `5+7` the split gets too uneven to pay.

`5+7:C` matches `5+7` to 0.03 and adds nothing the `6+6` pair does not already show.

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
  experiment.py  the pipeline the three scripts share
scripts/
  experiment_*.py        one per experiment, eight lines each
  visualize_palette.py   render any one JSON
```

- **The encoding** makes hues a phase plus softmax gaps summing to 360°, which removes
  the permutation symmetry. Chroma is a fraction of the worst-hue limit for its slot, so
  every candidate is in gamut by construction and the search needs no penalty term. A
  whole CMA-ES population is scored in one batched call.
- **The polish** solves `maximize t` subject to `ΔE00 ≥ t`, which is smooth where the raw
  `min` is not. Worth about 2%.
- **The JSON** stores only what cannot be recomputed: the layout, 12 OKLCh triples, the
  settings, and the two headline numbers. About 2.3 KB. Hex, the ΔE matrix and the binding
  pairs are derived on load in roughly 1 ms, so a stored number can never drift from the
  palette it describes.
- **The color math** re-anchors Oklab's LMS matrix onto sRGB's own white. Without it,
  white lands at Oklab L=1.0003 and the gamut boundary moves by 0.1%, enough to change a
  hex digit. `color.py` says why at length.

Run `uv run pytest` for the checks. The color math is cross-checked against `coloraide`,
an independent implementation.
