"""5+5+2: three lightnesses over two chromas, with the light rings welded to one chroma.

The `5+7` family gives its dark half and its light half a chroma each. This splits that
light half across two lightnesses and keeps both halves on the one chroma, so the palette
still reads as two saturations rather than three. Written `(0, 1, 1)`: ring 0 has its own
chroma, rings 1 and 2 share the second.

Grouping is what keeps the small ring honest. Left with its own chroma, a two-color ring
buys separation by going pale, because a low chroma at an extreme lightness is far from
everything and costs the objective nothing. Welded to the five vivid colors it cannot,
since going pale would drag all five with it.

The lightness floor is a guard, not a target. Nothing reaches it: the rings settle at
0.488, 0.741 and 0.903. Without it the search prefers a basin that puts the two-color ring
at L=0.280, scoring 28.49 on colors too dark to ship.
"""

import sys

from palette_lab.experiment import main
from palette_lab.search import Layout

LAYOUT = Layout((5, 5, 2), chroma_groups=(0, 1, 1), lightness_floor=0.45)

if __name__ == "__main__":
    sys.exit(main(LAYOUT, description=__doc__))
