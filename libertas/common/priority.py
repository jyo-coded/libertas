"""Resource governor: run Libertas and ShadowNet below normal priority so the laptop stays usable."""
from __future__ import annotations

import os


def lower_priority() -> None:
    try:
        import psutil

        proc = psutil.Process()
        if os.name == "nt":
            proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        else:
            proc.nice(10)
    except Exception:  # never fail startup over priority
        pass
