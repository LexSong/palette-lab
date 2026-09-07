"""Bright 12: twelve independent lightnesses inside a band, all on one chroma.

Every other layout here groups colors into rings that share a lightness. This gives each
color its own, and welds all twelve to a single chroma instead. That is the opposite
trade: no tier structure, perfect saturation consistency.

The band is what makes it. A floor alone holds one end, and the search spends the other:
given `L >= 0.60` it puts a color at L=0.961, which buys separation that a dimmed screen
cannot show and is invisible on white. Closing the top at 0.85 costs 2.1% of the minimum
and keeps every color in the range a dark or dimmed display actually renders.

So this is the palette for a dark background, and it is not the palette for paper. At 10%
backlight its worst pair holds 10.6 against 9.2 for `6+6` and 8.5 for `5+7`, because
neither of those has a floor and their darkest colors crush toward black. On white it is
the weakest of the four. That is deliberate.

One chroma across twelve free lightnesses costs less than one chroma across three rings.
A tier's shared chroma is capped by the worst hue anywhere on it, so the fewer colors per
tier, the higher the ceiling: `5+5+2` on one chroma manages 0.096, this manages 0.135.
"""

import sys

from palette_lab.experiment import main
from palette_lab.search import Layout

LAYOUT = Layout(
    (1,) * 12,
    chroma_groups=(0,) * 12,
    lightness_floor=0.60,
    lightness_ceiling=0.85,
    label="bright12",
)

if __name__ == "__main__":
    sys.exit(main(LAYOUT, description=__doc__))
