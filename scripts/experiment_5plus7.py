"""5+7: an uneven split, five colors on the inner ring and seven on the outer.

Reaches 24.85, just under 6+6. Kept because it is the one experiment where the two rings
take clearly different chromas, 0.096 against 0.153, so it shows what the search does
when it is not free to make both rings alike.
"""

import sys

from palette_lab.experiment import main
from palette_lab.search import Layout

LAYOUT = Layout((5, 7))

if __name__ == "__main__":
    sys.exit(main(LAYOUT, description=__doc__))
