"""QuantForge Background Monitor -- main entry point.

Modes:
  lite: Scan every 15 min. On HIGH/CRITICAL signal -> LLM analysis.
  full: Lite + scheduled briefings + news scraping + FinBERT + event detection.

Usage:
    python -m quantforge.monitor.monitor --config ~/.quantforge/config.yaml
"""
import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime

from quantforge.config import load_config, validate_monitor_config
from quantforge.monitor.secure_logger import setup_logging
from quantforge.monitor.alpaca_stream import AlpacaStream
from quantforge.monitor.pipeline import AnalysisPipeline
from quantforge.notify import create_notifier
from quantforge.providers.router import LLMRouter
from quantforge.secrets import SecretManager
from quantforge.safe_exceptions import install_exception_hooks

logger = logging.getLogger(__name__)


class TradeMonitor:
    """Background monitor with Lite/Full mode switching."""

    def __init__(self, config: dict):
        self.config = config
        monitor_cfg = validate_monitor_config(config.get("monitor", {}))
        self.requested_mode = monitor_cfg["monitor_mode"]
        self.scan_interval = monitor_cfg["scan_interval_minutes"] * 60
        self.briefing_schedule = monitor_cfg.get("briefing_schedule", [])
        self.briefing_tz = monitor_cfg.get("briefing_timezone", "Asia/Taipei")

        # Core components (always available)
        from quantforge.monitor.scanner import WatchlistScanner
        self.scanner = WatchlistScanner(config)
        self.alpaca = AlpacaStream()

        self.notifier = create_notifier(config)

        # LLM router
        self.llm_router = LLMRouter()

        # FinBERT (Full mode only)
        self.finbert = None
        self.news_scraper = None
        self.event_detector = None

        # Determine actual mode (may downgrade from full -> lite)
        self.mode = self._resolve_mode(monitor_cfg)

        # Analysis pipeline
        self.pipeline = AnalysisPipeline(
            config, notifier=self.notifier,
            llm_router=self.llm_router, finbert=self.finbert,
        )

        # Full mode components
        if self.mode == "full":
            self._init_full_mode(monitor_cfg)

        self._running = False
        self._briefing_fired: dict[str, str] = {}

    def _resolve_mode(self, monitor_cfg: dict) -> str:
        """Check if full mode requirements are met, fallback to lite if not."""
        if self.requested_mode != "full":
            return "lite"

        # Full mode requires LLM
        if not self.llm_router.has_providers():
            logger.error(
                "Full mode requires LLM provider (Claude or Gemini). "
                "Set ANTHROPIC_API_KEY or GOOGLE_AI_API_KEY in ~/.quantforge/.env. "
                "Falling back to lite mode."
            )
            return "lite"

        # Full mode requires FinBERT
        try:
            from quantforge.finbert.analyzer import FinBERTAnalyzer
            self.finbert = FinBERTAnalyzer()
            self.finbert._load()
        except Exception:
            logger.error(
                "Full mode requires FinBERT model. "
                "Install: python -m quantforge.finbert.download. "
                "Or switch to lite mode: monitor_mode: lite. "
                "Falling back to lite mode."
            )
            self.finbert = None
            return "lite"

        return "full"

    def _init_full_mode(self, monitor_cfg: dict):
        """Initialize Full mode components: news scraper, event detector."""
        from quantforge.monitor.news_scraper import NewsScraper
        from quantforge.monitor.event_detector import EventDetector

        watchlist = self.config.get("watchlist", {})
        all_symbols = watchlist.get("US", []) + watchlist.get("TW", [])
        self.news_scraper = NewsScraper(symbols=all_symbols)

        event_cfg = monitor_cfg.get("event_detector", {})
        cooldown_cfg = monitor_cfg.get("cooldown", {})
        self.event_detector = EventDetector(event_cfg, cooldown_cfg)

    def _startup_check(self) -> list[str]:
        """Check all components and return warning messages."""
        warnings = []

        if not self.notifier.is_configured():
            warnings.append(
                "WARNING: Telegram not configured -- alerts will only appear in logs. "
                "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in ~/.quantforge/.env"
            )

        if not self.llm_router.has_providers():
            warnings.append(
                "WARNING: No LLM provider available -- running quant-only mode "
                "(no advisor analysis). "
                "Set ANTHROPIC_API_KEY in ~/.quantforge/.env"
            )

        if not self.alpaca.is_configured():
            warnings.append(
                "WARNING: Alpaca not configured -- no real-time US streaming, "
                "using polling only. "
                "Set ALPACA_DATA_KEY and ALPACA_DATA_SECRET in ~/.quantforge/.env"
            )

        if self.requested_mode == "full" and self.mode == "lite":
            warnings.append(
                "WARNING: Requested full mode but requirements not met -- "
                "running in lite mode."
            )

        return warnings

    def _startup_summary(self) -> str:
        """Generate startup summary message."""
        watchlist = self.config.get("watchlist", {})
        us_count = len(watchlist.get("US", []))
        tw_count = len(watchlist.get("TW", []))

        providers = self.llm_router.available_providers
        llm_status = f"LLM: {', '.join(providers)}" if providers else "LLM: none"

        lines = [
            f"QuantForge Monitor started ({self.mode} mode)",
            f"{'Y' if self.notifier.is_configured() else 'N'} Telegram",
            f"{'Y' if providers else 'N'} {llm_status}",
            f"{'Y' if self.finbert else 'N'} FinBERT",
            f"{'Y' if self.alpaca.is_configured() else 'N'} Alpaca real-time",
            f"Watchlist: {us_count} US + {tw_count} TW",
            f"Scan interval: {self.scan_interval // 60} min",
        ]
        return "\n".join(lines)

    async def run(self):
        """Start the monitor. Runs until stopped."""
        self._running = True

        for warning in self._startup_check():
            logger.warning(warning)

        summary = self._startup_summary()
        logger.info(summary)
        self.notifier.send_text(summary)

        self.pipeline.report_store.cleanup()

        tasks = [self._scheduled_loop()]

        if self.mode == "full":
            tasks.append(self._briefing_loop())
            tasks.append(self._event_detector_loop())

        if self.alpaca.is_configured():
            us_symbols = self.config.get("watchlist", {}).get("US", [])
            if us_symbols:
                self.alpaca.subscribe_bars(us_symbols, handler=self._on_realtime_bar)
                tasks.append(self.alpaca.run())

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Monitor shutting down...")
        finally:
            self._running = False
            await self.alpaca.stop()

    async def stop(self):
        self._running = False
        await self.alpaca.stop()

    async def _scheduled_loop(self):
        """Scan watchlist every scan_interval seconds."""
        while self._running:
            await self._run_scheduled_scan()
            await asyncio.sleep(self.scan_interval)

    async def _run_scheduled_scan(self):
        """Run full watchlist scan and trigger analysis on signals."""
        logger.info("Running scheduled watchlist scan...")
        try:
            signals = self.scanner.scan_all()
            if signals:
                logger.info("Found %d signals", len(signals))
                for signal in signals:
                    self.notifier.send_signal(signal)
                    asyncio.create_task(self.pipeline.run(signal))
            else:
                logger.info("No signals detected")
        except Exception as e:
            logger.error("Scan error: %s", type(e).__name__)

    async def _briefing_loop(self):
        """Full mode: scheduled briefings at configured times."""
        while self._running:
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            today = now.strftime("%Y-%m-%d")

            for scheduled_time in self.briefing_schedule:
                fire_key = f"{scheduled_time}"
                already_fired = self._briefing_fired.get(fire_key)

                if current_time == scheduled_time and already_fired != today:
                    self._briefing_fired[fire_key] = today
                    briefing_type = self._briefing_type_for_time(scheduled_time)
                    asyncio.create_task(
                        self.pipeline.run_briefing(briefing_type))

            await asyncio.sleep(30)

    async def _event_detector_loop(self):
        """Full mode: detect critical events from news and price changes."""
        while self._running:
            try:
                articles = await self.news_scraper.fetch_all()
                if articles and self.finbert:
                    scored = self.finbert.score_batch([
                        {"text": a.text, "symbol": a.symbol,
                         "source": a.source, "published": a.published}
                        for a in articles
                    ])
                    events = self.event_detector.detect_from_news(scored)
                    for event in events:
                        asyncio.create_task(
                            self.pipeline.run_recalc(event.symbol, event.trigger))
            except Exception as e:
                logger.error("Event detection error: %s", type(e).__name__)

            await asyncio.sleep(self.scan_interval)

    async def _on_realtime_bar(self, bar: dict):
        """Handle real-time bar from Alpaca stream."""
        symbol = bar.get("symbol", "")
        try:
            signals = self.scanner.scan_symbol(symbol, market="US")
            for signal in signals:
                self.notifier.send_signal(signal)
                asyncio.create_task(self.pipeline.run(signal))
        except Exception as e:
            logger.error("Real-time scan error for %s: %s", symbol, type(e).__name__)

    @staticmethod
    def _briefing_type_for_time(time_str: str) -> str:
        """Map scheduled time to briefing type."""
        hour = int(time_str.split(":")[0])
        if hour < 12:
            return "tw_premarket"
        elif hour < 18:
            return "tw_close"
        else:
            return "us_premarket"


def main():
    parser = argparse.ArgumentParser(description="QuantForge Background Monitor")
    parser.add_argument("--config",
                        default=os.path.expanduser("~/.quantforge/config.yaml"))
    parser.add_argument("--log-dir",
                        default=os.path.expanduser("~/.quantforge/logs"))
    args = parser.parse_args()

    install_exception_hooks()
    setup_logging(log_dir=args.log_dir)

    try:
        config = load_config(args.config)
    except FileNotFoundError:
        logger.error("Config not found: %s -- run install.sh first", args.config)
        sys.exit(1)

    monitor = TradeMonitor(config)
    try:
        asyncio.run(monitor.run())
    except KeyboardInterrupt:
        logger.info("Monitor stopped by user")


if __name__ == "__main__":
    main()
