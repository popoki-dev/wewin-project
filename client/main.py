"""WeWin desktop client.

    python -m client.main      (from the repository root)
    python client/main.py
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    # Run as a script: make the repository root importable.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from client.app.bootstrap import run  # noqa: E402

if __name__ == "__main__":
    sys.exit(run())
