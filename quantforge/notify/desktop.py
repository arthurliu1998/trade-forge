"""Desktop notification backend using notify-send (Linux)."""
import logging
import shutil
import subprocess

from quantforge.notify.base import BaseNotifier
from quantforge.notify.telegram import format_signal_message
from quantforge.signals.engine import Signal

logger = logging.getLogger(__name__)


class DesktopNotifier(BaseNotifier):
    def __init__(self, sensitivity: str = "medium"):
        self.sensitivity = sensitivity

    def is_configured(self) -> bool:
        return shutil.which("notify-send") is not None

    def send_signal(self, signal: Signal) -> bool:
        if not self.is_configured():
            return False
        msg = format_signal_message(signal, self.sensitivity)
        return self.send_text(msg)

    def send_text(self, text: str) -> bool:
        if not self.is_configured():
            return False
        try:
            subprocess.run(
                ["notify-send", "QuantForge", text],
                timeout=5,
                check=False,
            )
            return True
        except Exception as e:
            logger.warning("Desktop notification failed: %s", type(e).__name__)
            return False
