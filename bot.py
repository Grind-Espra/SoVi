"""Compatibility entry point.

The active SoVi implementation lives in ``app/`` and is started by ``main.py``.
This file is kept so older deployment commands using ``python bot.py`` continue
to launch the same bot instead of the obsolete legacy implementation.
"""

import asyncio

from app.main import main


if __name__ == "__main__":
    asyncio.run(main())
