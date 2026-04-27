import pytest
import yaml
from quantforge.config import SecureConfig, load_config


def test_secure_config_masks_sensitive_keys():
    cfg = SecureConfig({"api_key": "sk-secret-123", "name": "test"})
    text = repr(cfg)
    assert "sk-secret-123" not in text
    assert "REDACTED" in text
    assert "test" in text


def test_secure_config_str_also_masked():
    cfg = SecureConfig({"token": "bot12345:abc", "debug": True})
    assert "bot12345" not in str(cfg)


def test_load_config_returns_secure_config(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.dump({"watchlist": {"US": ["AAPL"]}}))
    cfg = load_config(str(cfg_file))
    assert isinstance(cfg, SecureConfig)
    assert cfg["watchlist"]["US"] == ["AAPL"]


def test_load_config_rejects_inline_telegram_token(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.dump({
        "notification": {"telegram": {"bot_token": "bot123456:REAL_TOKEN_HERE", "chat_id": "12345"}}
    }))
    with pytest.raises(ValueError, match="must use env ref"):
        load_config(str(cfg_file))


def test_load_config_allows_env_ref(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.dump({
        "notification": {"telegram": {"bot_token": "${TELEGRAM_BOT_TOKEN}", "chat_id": "${TELEGRAM_CHAT_ID}"}}
    }))
    cfg = load_config(str(cfg_file))
    assert cfg["notification"]["telegram"]["bot_token"] == "${TELEGRAM_BOT_TOKEN}"


class TestMonitorConfig:
    def test_valid_monitor_config(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("""
watchlist:
  US: [AAPL]
  TW: ["2330"]
signals:
  ma_crossover: [20, 60]
monitor:
  monitor_mode: full
  scan_interval_minutes: 15
  briefing_timezone: "Asia/Taipei"
  briefing_schedule: ["08:30", "14:00", "21:00"]
  cooldown:
    same_symbol_minutes: 120
    daily_recalc_limit: 5
""")
        from quantforge.config import load_config
        config = load_config(str(cfg))
        assert config["monitor"]["monitor_mode"] == "full"
        assert config["monitor"]["scan_interval_minutes"] == 15

    def test_missing_monitor_section_uses_defaults(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("watchlist:\n  US: [AAPL]\n")
        from quantforge.config import load_config
        config = load_config(str(cfg))
        assert "monitor" not in config

    def test_invalid_monitor_mode_rejected(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("""
watchlist:
  US: [AAPL]
monitor:
  monitor_mode: turbo
""")
        from quantforge.config import load_config, validate_monitor_config
        config = load_config(str(cfg))
        validated = validate_monitor_config(config.get("monitor", {}))
        assert validated["monitor_mode"] == "lite"
