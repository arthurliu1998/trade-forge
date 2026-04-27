"""
Secure configuration loader.
- SecureConfig masks sensitive values in repr/str
- load_config rejects inline secrets in YAML
"""
import yaml

_SENSITIVE_SUBSTRINGS = ("key", "token", "secret", "password")


class SecureConfig(dict):
    def __repr__(self):
        masked = {}
        for k, v in self.items():
            if isinstance(v, str) and any(s in k.lower() for s in _SENSITIVE_SUBSTRINGS):
                masked[k] = "***REDACTED***"
            else:
                masked[k] = v
        return f"SecureConfig({masked})"

    def __str__(self):
        return self.__repr__()


def load_config(path: str) -> SecureConfig:
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    _validate_no_inline_secrets(raw)
    return SecureConfig(raw)


def _validate_no_inline_secrets(cfg: dict) -> None:
    telegram = cfg.get("notification", {}).get("telegram", {})
    for field in ("bot_token", "chat_id"):
        val = telegram.get(field, "")
        if val and not val.startswith("${"):
            raise ValueError(
                f"config.yaml: notification.telegram.{field} must use env ref "
                f"(e.g., '${{TELEGRAM_BOT_TOKEN}}'), not inline values. "
                f"Move the value to .env or keyring."
            )


MONITOR_DEFAULTS = {
    "monitor_mode": "lite",
    "scan_interval_minutes": 15,
    "briefing_timezone": "Asia/Taipei",
    "briefing_schedule": ["08:30", "14:00", "21:00"],
    "cooldown": {
        "same_symbol_minutes": 120,
        "daily_recalc_limit": 5,
    },
    "event_detector": {
        "finbert_threshold_pos": 0.9,
        "finbert_threshold_neg": -0.85,
        "keywords": ["earnings", "merger", "investigation", "delisting", "upgrade", "downgrade"],
        "article_cluster_count": 3,
        "article_cluster_window_min": 15,
    },
    "reports": {
        "retention_days": 30,
        "output_dir": "~/.quantforge/reports",
    },
}

VALID_MODES = ("lite", "full")


def validate_monitor_config(monitor_cfg: dict) -> dict:
    result = {}
    for key, default in MONITOR_DEFAULTS.items():
        result[key] = monitor_cfg.get(key, default)
    if result["monitor_mode"] not in VALID_MODES:
        result["monitor_mode"] = "lite"
    if not isinstance(result["scan_interval_minutes"], (int, float)):
        result["scan_interval_minutes"] = 15
    return result
