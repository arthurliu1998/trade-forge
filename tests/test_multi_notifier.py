from unittest.mock import MagicMock

from quantforge.notify.base import BaseNotifier
from quantforge.notify.multi import MultiNotifier
from quantforge.signals.engine import Signal


def _make_notifier(configured=True, send_ok=True):
    n = MagicMock(spec=BaseNotifier)
    n.is_configured.return_value = configured
    n.send_text.return_value = send_ok
    n.send_signal.return_value = send_ok
    return n


class TestMultiNotifier:
    def test_is_configured_any(self):
        n1 = _make_notifier(configured=False)
        n2 = _make_notifier(configured=True)
        multi = MultiNotifier([n1, n2])
        assert multi.is_configured() is True

    def test_is_configured_none(self):
        n1 = _make_notifier(configured=False)
        multi = MultiNotifier([n1])
        assert multi.is_configured() is False

    def test_send_text_fans_out(self):
        n1 = _make_notifier(configured=True)
        n2 = _make_notifier(configured=True)
        multi = MultiNotifier([n1, n2])
        result = multi.send_text("hello")
        assert result is True
        n1.send_text.assert_called_once_with("hello")
        n2.send_text.assert_called_once_with("hello")

    def test_send_text_skips_unconfigured(self):
        n1 = _make_notifier(configured=False)
        n2 = _make_notifier(configured=True)
        multi = MultiNotifier([n1, n2])
        multi.send_text("hello")
        n1.send_text.assert_not_called()
        n2.send_text.assert_called_once()

    def test_send_signal_fans_out(self):
        sig = Signal("AAPL", "rsi", "HIGH", "msg", 1.0, "bullish")
        n1 = _make_notifier(configured=True)
        multi = MultiNotifier([n1])
        result = multi.send_signal(sig)
        assert result is True
        n1.send_signal.assert_called_once_with(sig)

    def test_empty_notifiers(self):
        multi = MultiNotifier([])
        assert multi.is_configured() is False
        assert multi.send_text("hello") is False
