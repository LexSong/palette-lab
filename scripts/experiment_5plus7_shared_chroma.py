"""5+7 with one chroma shared by both rings.

The uneven counterpart to experiment_6plus6_shared_chroma. It is the harder case for
sharing: left free, 5+7 gives its two rings clearly different chromas, 0.096 and 0.153,
so one shared value has to give up more than it does on 6+6, where the two land within
0.004 of each other.

This exists to answer whether sharing costs more when the split is uneven.
"""

import sys

from palette_lab.experiment import main
from palette_lab.search import Layout

LAYOUT = Layout((5, 7), shared_chroma=True)

if __name__ == "__main__":
    sys.exit(main(LAYOUT, description=__doc__))
