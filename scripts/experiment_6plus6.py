"""6+6: two rings of six, each ring free to pick its own chroma.

The best exact separation of the three, 25.12 delta-E00. Its two chromas land within
0.004 of each other, which is what prompted the shared-chroma variant.

The two rings also end up on nearly the same hues, within 4 degrees. That is not a bug.
Both rings face the same sRGB gamut shape and the same CIEDE2000 hue non-uniformity, so
each independently reaches the same answer.
"""

import sys

from palette_lab.experiment import main
from palette_lab.search import Layout

LAYOUT = Layout((6, 6))

if __name__ == "__main__":
    sys.exit(main(LAYOUT, description=__doc__))
