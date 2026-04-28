"""Discord webhook notification backend."""
import logging

import requests

from quantforge.notify.base import BaseNotifier
from quantforge.notify.telegram import format_signal_message
from quantforge.signals.engine import Signal

logger = logging.getLogger(__name__)


class DiscordNotifier(BaseNotifier):
    def __init__(self, webhook_url: str, sensitivity: str = "medium"):
        self._webhook_url = webhook_url
        self.sensitivity = sensitivity

    def is_configured(self) -> bool:
        return bool(self._webhook_url)

    def send_signal(self, signal: Signal) -> bool:
        if not self.is_configured():
            return False
        msg = format_signal_message(signal, self.sensitivity)
        return self.send_text(msg)

    def send_text(self, text: str) -> bool:
        if not self.is_configured():
            return False
        try:
            resp = requests.post(
                self._webhook_url,
                json={"content": text},
                timeout=10,
            )
            if resp.status_code in (200, 204):
                return True
            logger.warning("Discord send failed: HTTP %d", resp.status_code)
            return False
        except Exception as e:
            logger.warning("Discord send failed: %s", type(e).__name__)
            return False
