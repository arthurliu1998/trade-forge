from unittest.mock import patch, MagicMock

from quantforge.notify.discord import DiscordNotifier
from quantforge.signals.engine import Signal


class TestDiscordNotifier:
    def test_not_configured_without_url(self):
        n = DiscordNotifier(webhook_url="")
        assert n.is_configured() is False

    def test_configured_with_url(self):
        n = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/123/abc")
        assert n.is_configured() is True

    def test_send_text_posts_to_webhook(self):
        mock_resp = MagicMock(status_code=204)
        with patch("quantforge.notify.discord.requests.post", return_value=mock_resp) as mock_post:
            n = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/123/abc")
            result = n.send_text("test message")
            assert result is True
            mock_post.assert_called_once_with(
                "https://discord.com/api/webhooks/123/abc",
                json={"content": "test message"},
                timeout=10,
            )

    def test_send_text_returns_false_on_http_error(self):
        mock_resp = MagicMock(status_code=400)
        with patch("quantforge.notify.discord.requests.post", return_value=mock_resp):
            n = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/123/abc")
            assert n.send_text("test") is False

    def test_send_signal_formats_and_posts(self):
        sig = Signal("TSLA", "volume_spike", "CRITICAL", "Volume 3x", 3.0, "bullish")
        mock_resp = MagicMock(status_code=204)
        with patch("quantforge.notify.discord.requests.post", return_value=mock_resp) as mock_post:
            n = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/123/abc", sensitivity="low")
            result = n.send_signal(sig)
            assert result is True
            payload = mock_post.call_args[1]["json"]
            assert "TSLA" in payload["content"]

    def test_send_text_returns_false_when_not_configured(self):
        n = DiscordNotifier(webhook_url="")
        assert n.send_text("hello") is False
