"""
Shared logging configuration for all bots in the monorepo.

Why this module exists
----------------------
All three bots (leocard, newbie, profcom) will run as separate containers on a
single EC2 instance. When something breaks at 3am you need to answer:
  - Which bot produced this log line?
  - When exactly?
  - Severity?
  - And — can you grep across all three?

Keeping logging config here (instead of copy-pasting into each bot's entrypoint)
means one change applies everywhere.

How each bot uses it
--------------------
At the top of each bot's entrypoint (bot.py / main.py), replace the existing
``logging.basicConfig(...)`` call with::

    from shared.logging_config import setup_logging
    setup_logging(bot_name="leocard")  # or "newbie" / "profcom"

The ``shared/`` directory is mounted into every container at ``/app/shared``
(see docker-compose.yml) and added to PYTHONPATH.
"""

from __future__ import annotations

import logging
import os
import sys


def setup_logging(bot_name: str) -> logging.Logger:
    """
    Configure the root logger for a bot process and return a named logger.

    Parameters
    ----------
    bot_name:
        Short identifier of the bot ("leocard", "newbie", "profcom"). It is
        embedded into every log record so that when all three containers' logs
        are tailed together (e.g. ``docker compose logs -f``) you can tell them
        apart at a glance.

    Returns
    -------
    logging.Logger
        A logger named after the bot, ready to use.
    """
    # Read desired level from env — falls back to INFO. This way you can crank
    # a single container to DEBUG in production without touching code.
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    # stdout-only, 12-factor style — `docker compose logs` just works.
    fmt = logging.Formatter(
        f"%(asctime)s [{bot_name}] %(levelname)s %(name)s: %(message)s"
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)

    # Silence chatty third-party loggers.
    for noisy in ("httpx", "telegram", "aiogram", "gspread", "google", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return logging.getLogger(bot_name)
