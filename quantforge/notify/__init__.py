"""Notification subsystem with pluggable backends."""
import logging

from quantforge.notify.base import BaseNotifier
from quantforge.notify.multi import MultiNotifier

logger = logging.getLogger(__name__)

_BACKEND_BUILDERS = {
    "telegram": "_build_telegram",
    "desktop": "_build_desktop",
    "discord": "_build_discord",
}


def create_notifier(config: dict) -> BaseNotifier:
    """Build a notifier from config. Returns MultiNotifier wrapping all backends."""
    from quantforge.secrets import SecretManager

    notif_cfg = config.get("notification", {})
    backends = notif_cfg.get("backends", ["telegram"])
    sensitivity = notif_cfg.get("sensitivity", "medium")

    notifiers = []
    for name in backends:
        builder = _BACKEND_BUILDERS.get(name)
        if builder is None:
            logger.warning("Unknown notification backend: %s", name)
            continue
        n = globals()[builder](sensitivity, SecretManager)
        notifiers.append(n)

    if not notifiers:
        logger.warning("No notification backends configured")
        return MultiNotifier([])

    return MultiNotifier(notifiers)


def _build_telegram(sensitivity: str, secrets) -> BaseNotifier:
    from quantforge.notify.telegram import TelegramNotifier
    token = secrets.get("TELEGRAM_BOT_TOKEN")
    chat_id = secrets.get("TELEGRAM_CHAT_ID")
    return TelegramNotifier(token, chat_id, sensitivity)


def _build_desktop(sensitivity: str, secrets) -> BaseNotifier:
    from quantforge.notify.desktop import DesktopNotifier
    return DesktopNotifier(sensitivity)


def _build_discord(sensitivity: str, secrets) -> BaseNotifier:
    from quantforge.notify.discord import DiscordNotifier
    webhook_url = secrets.get("DISCORD_WEBHOOK_URL")
    return DiscordNotifier(webhook_url, sensitivity)
