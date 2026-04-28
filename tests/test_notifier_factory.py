from unittest.mock import patch, MagicMock

from quantforge.notify import create_notifier
from quantforge.notify.multi import MultiNotifier
from quantforge.notify.telegram import TelegramNotifier
from quantforge.notify.desktop import DesktopNotifier
from quantforge.notify.discord import DiscordNotifier


def _mock_secrets(return_value=""):
    sm = MagicMock()
    sm.get.return_value = return_value
    return sm


class TestCreateNotifier:
    def test_default_backend_is_telegram(self):
        with patch("quantforge.secrets.SecretManager", _mock_secrets()):
            result = create_notifier({"notification": {}})
            assert isinstance(result, MultiNotifier)
            assert len(result._notifiers) == 1
            assert isinstance(result._notifiers[0], TelegramNotifier)

    def test_desktop_backend(self):
        with patch("quantforge.secrets.SecretManager", _mock_secrets()):
            result = create_notifier({"notification": {"backends": ["desktop"]}})
            assert isinstance(result._notifiers[0], DesktopNotifier)

    def test_discord_backend(self):
        with patch("quantforge.secrets.SecretManager", _mock_secrets("https://discord.com/api/webhooks/123/abc")):
            result = create_notifier({"notification": {"backends": ["discord"]}})
            assert isinstance(result._notifiers[0], DiscordNotifier)

    def test_multiple_backends(self):
        with patch("quantforge.secrets.SecretManager", _mock_secrets()):
            result = create_notifier({
                "notification": {"backends": ["desktop", "telegram"]}
            })
            assert len(result._notifiers) == 2
            assert isinstance(result._notifiers[0], DesktopNotifier)
            assert isinstance(result._notifiers[1], TelegramNotifier)

    def test_unknown_backend_skipped(self):
        with patch("quantforge.secrets.SecretManager", _mock_secrets()):
            result = create_notifier({
                "notification": {"backends": ["unknown_backend"]}
            })
            assert len(result._notifiers) == 0

    def test_sensitivity_passed_through(self):
        with patch("quantforge.secrets.SecretManager", _mock_secrets()):
            result = create_notifier({
                "notification": {"backends": ["desktop"], "sensitivity": "high"}
            })
            assert result._notifiers[0].sensitivity == "high"
