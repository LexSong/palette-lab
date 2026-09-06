"""6+6 with one chroma shared by both rings.

A real constraint, not a relabelling: the single C is capped by the worst hue anywhere in
the palette rather than the worst hue on each ring, so a ring that could have carried
more chroma gives it up.

It costs almost nothing, 25.07 against 6+6's 25.12, and it survives 8-bit quantization
better, 24.88 against 24.76. All 12 colors land on one circle in the a/b plane.
"""

import sys

from palette_lab.experiment import main
from palette_lab.search import Layout

LAYOUT = Layout((6, 6), shared_chroma=True)

if __name__ == "__main__":
    sys.exit(main(LAYOUT, description=__doc__))
