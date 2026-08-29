"""
Read-only helper for the shared notification chats list.

The list itself is managed by Profcom's /notify command — it writes to
notification_chats.json. All bots in the monorepo read from it via this
module to know where to broadcast operational notifications.

The file lives at /app/notification_chats.json inside every container
(bind-mounted from data/shared/notification_chats.json on the host).
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

NOTIFICATION_FILE = "notification_chats.json"


def get_notification_chats() -> set[int]:
    """Return the set of Telegram chat IDs subscribed to notifications."""
    if not os.path.exists(NOTIFICATION_FILE):
        return set()
    try:
        with open(NOTIFICATION_FILE) as f:
            data = json.load(f)
            return set(data.get("chat_ids", []))
    except Exception as e:
        logger.error("Failed to read %s: %s", NOTIFICATION_FILE, e)
        return set()
