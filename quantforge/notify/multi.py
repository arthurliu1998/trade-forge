"""Multi-notifier that fans out to all configured backends."""
import logging

from quantforge.notify.base import BaseNotifier
from quantforge.signals.engine import Signal

logger = logging.getLogger(__name__)


class MultiNotifier(BaseNotifier):
    def __init__(self, notifiers: list[BaseNotifier]):
        self._notifiers = notifiers

    def is_configured(self) -> bool:
        return any(n.is_configured() for n in self._notifiers)

    def send_signal(self, signal: Signal) -> bool:
        ok = False
        for n in self._notifiers:
            if n.is_configured():
                ok = n.send_signal(signal) or ok
        return ok

    def send_text(self, text: str) -> bool:
        ok = False
        for n in self._notifiers:
            if n.is_configured():
                ok = n.send_text(text) or ok
        return ok
