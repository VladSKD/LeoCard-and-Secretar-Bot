import json
import os
import logging

NOTIFICATION_FILE = "notification_chats.json"

logger = logging.getLogger(__name__)

_initialized = False


def _init_from_env():
    """Load notification chats from env var on first access.

    Similar to google_services._init_auth_files(): on Railway the
    file system is ephemeral, so we persist the chat list in the
    NOTIFICATION_CHATS env var and write it to a local file once
    per process start.
    """
    global _initialized
    if _initialized:
        return
    _initialized = True

    env_data = os.environ.get("NOTIFICATION_CHATS")
    if env_data:
        try:
            with open(NOTIFICATION_FILE, "w") as f:
                f.write(env_data)
        except Exception as e:
            logger.error(f"Помилка при записі NOTIFICATION_CHATS у файл: {e}")


def _load_chats() -> set:
    _init_from_env()
    if os.path.exists(NOTIFICATION_FILE):
        try:
            with open(NOTIFICATION_FILE, "r") as f:
                data = json.load(f)
                return set(data.get("chat_ids", []))
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Помилка при завантаженні чатів сповіщень: {e}")
    return set()


def _save_chats(chat_ids: set):
    content = json.dumps({"chat_ids": list(chat_ids)})
    with open(NOTIFICATION_FILE, "w") as f:
        f.write(content)
    # Also update the env var so it can be read by _init_from_env on next restart.
    # NOTE: This updates the in-process env only. On Railway, the env var
    # NOTIFICATION_CHATS must be set once manually via the dashboard with
    # the initial chat IDs, or left empty. After the first /notify command
    # the file will exist for the lifetime of the current deploy. To truly
    # persist across redeploys, copy the value from the logs or set it
    # manually on Railway.
    os.environ["NOTIFICATION_CHATS"] = content
    logger.info(f"NOTIFICATION_CHATS env var оновлено: {content}")


def add_chat(chat_id: int) -> bool:
    chats = _load_chats()
    if chat_id in chats:
        return False
    chats.add(chat_id)
    _save_chats(chats)
    return True


def remove_chat(chat_id: int) -> bool:
    chats = _load_chats()
    if chat_id not in chats:
        return False
    chats.discard(chat_id)
    _save_chats(chats)
    return True


def is_chat_subscribed(chat_id: int) -> bool:
    return chat_id in _load_chats()


def get_all_chats() -> set:
    return _load_chats()
