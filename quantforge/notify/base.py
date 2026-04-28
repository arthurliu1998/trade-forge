"""Base notifier interface for all notification backends."""
import logging

from quantforge.signals.engine import Signal

logger = logging.getLogger(__name__)


class BaseNotifier:
    """Abstract base for notification backends."""

    def is_configured(self) -> bool:
        return False

    def send_signal(self, signal: Signal) -> bool:
        raise NotImplementedError

    def send_text(self, text: str) -> bool:
        raise NotImplementedError
