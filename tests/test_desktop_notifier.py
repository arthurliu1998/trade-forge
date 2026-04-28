from unittest.mock import patch

from quantforge.notify.desktop import DesktopNotifier
from quantforge.signals.engine import Signal


class TestDesktopNotifier:
    def test_not_configured_without_notify_send(self):
        with patch("quantforge.notify.desktop.shutil.which", return_value=None):
            n = DesktopNotifier()
            assert n.is_configured() is False

    def test_configured_with_notify_send(self):
        with patch("quantforge.notify.desktop.shutil.which", return_value="/usr/bin/notify-send"):
            n = DesktopNotifier()
            assert n.is_configured() is True

    def test_send_text_calls_notify_send(self):
        with patch("quantforge.notify.desktop.shutil.which", return_value="/usr/bin/notify-send"), \
             patch("quantforge.notify.desktop.subprocess.run") as mock_run:
            n = DesktopNotifier()
            result = n.send_text("hello")
            assert result is True
            mock_run.assert_called_once_with(
                ["notify-send", "QuantForge", "hello"],
                timeout=5,
                check=False,
            )

    def test_send_signal_formats_and_sends(self):
        sig = Signal("AAPL", "rsi_oversold", "HIGH", "RSI at 20", 20.0, "bullish")
        with patch("quantforge.notify.desktop.shutil.which", return_value="/usr/bin/notify-send"), \
             patch("quantforge.notify.desktop.subprocess.run") as mock_run:
            n = DesktopNotifier(sensitivity="high")
            result = n.send_signal(sig)
            assert result is True
            args = mock_run.call_args[0][0]
            assert args[0] == "notify-send"
            assert "AAPL" in args[2]

    def test_send_text_returns_false_when_not_configured(self):
        with patch("quantforge.notify.desktop.shutil.which", return_value=None):
            n = DesktopNotifier()
            assert n.send_text("hello") is False
