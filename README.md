# Twelve Colors, No Confusion

Twelve categories on one chart, and every one of them tells itself apart.

## 5+5+2 — The Clearest

![5+5+2](images/5+5+2.png)

```
#904839  #f58d3d  #ffde54  #705f00  #6dc364  #007153
#00fff7  #00688f  #16b8ff  #b993ff  #724e8a  #fc7d92
```

The clearest twelve here, by 12%. Five muted colors, five vivid ones, and two
bright ones on top. Twelve lines on one chart, and not one of them needs a
second look.

## 6+6 — The Most Uniform

![6+6](images/6+6.png)

```
#ff9ca9  #ab505e  #a45c1d  #f5aa6b  #777600  #bac669
#00865c  #56d6bc  #61cbfb  #007aad  #7a60ad  #c7acff
```

Six light, six dark, every one at the same saturation. The most even-tempered
palette here, and the one that holds up best on a white page. Drop it into a
twelve-series chart and stop thinking about the legend.

## 5+7 — The Most Vivid

![5+7](images/5+7.png)

```
#a73f52  #f48870  #a34a00  #da9d33  #9cb74d  #2c7b2c
#00c6a8  #00bce8  #006bb1  #98a0ff  #7b4fa6  #e685bf
```

Same twelve slots, more color. An uneven split buys extra saturation, so the
chart comes out lively and still reads clean. Take this one when the deck has
to look good, not only work.

## Why and How

You have twelve things to plot and one chart to plot them in. Pick the colors
by hand and two of them always land too close, so your reader ends up looking
back at the legend to check which line was which. Most ready-made palettes
have the same problem — they hold up to about eight colors and quietly fall
apart after that.

**Every pair was checked, not just the palette as a whole.** Twelve colors
make 66 possible pairs. These were found by scoring all 66 and pushing the
*closest* one as far apart as it would go. Averages are the trap: a palette
can average beautifully while two of its colors stay twins. Here the weakest
pair is as strong as it can be, and the weakest pair is the only one your
reader will ever trip on.

**Brightness does the work hue cannot.** Ask hue alone to separate twelve
colors and the palette comes out about half as clear, because there is not
room for twelve distinguishable hues. Add a brightness difference and the eye
gets a second thing to sort by, so neighbors stop competing. `6+6` and `5+7`
use two brightness levels. `5+5+2` uses three, which is most of why it wins.

**They still look like a set.** `6+6` and `5+7` give every color the same
saturation. `5+5+2` uses two — one for its five muted colors and one shared by
the other seven — so it reads as two deliberate groups rather than twelve picks
off a color wheel. All of them sit inside sRGB, so nothing needs a wide-gamut
monitor and nothing dulls out on someone else's screen.

**Nothing is too dark to use.** No color goes below Oklab lightness 0.48, so
none of them turn to mud on a dimmed phone or a cheap projector.

**Where 5+5+2 gives ground is a white background.** Its two bright colors,
`#ffde54` and `#00fff7`, sit at 1.26:1 contrast there, so they hold up as filled
areas and bars and go too faint for thin lines or small text. `6+6` is the safer
pick on white, at 1.79:1 worst case. On a dark background `5+5+2` is the
strongest of the three.

Every palette is listed in hue order, swatch and code alike, so you can compare
them row against row.

## More Detail

Copy the twelve hex codes and you're done. If you want more, every
palette ships its full data — hue and chroma per color, which ring it sits on,
the CIEDE2000 matrix — in `results/*.json`, loaded by
`palette_lab.palette.load`:

```sh
uv run scripts/visualize_palette.py results/5+5+2.json
```

[EXPERIMENTS.md](EXPERIMENTS.md) has the exact scores, the ΔE00 matrices, the
layouts that were tried and dropped — including versions where each ring keeps
its own saturation — and how to regenerate all of it from scratch. It also
answers the strangest result of the search: on `6+6` the two rings land on
nearly the same hues, within 4°, which looks like a bug and is not.

## License

MIT, in [LICENSE](LICENSE) — that covers the code. The colors themselves are
twelve numbers, so take them and go.
