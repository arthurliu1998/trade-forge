"""Save analysis reports to local filesystem with auto-cleanup."""
import logging
import os
import shutil
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ReportStore:
    def __init__(self, base_dir: str = "~/.quantforge/reports",
                 retention_days: int = 30):
        self.base_dir = os.path.expanduser(base_dir)
        self.retention_days = retention_days

    def save(self, report_type: str, label: str, content: str) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        time_str = datetime.now().strftime("%H%M%S")
        day_dir = os.path.join(self.base_dir, today)
        os.makedirs(day_dir, exist_ok=True)
        filename = f"{label}-{time_str}-{report_type}.md"
        filepath = os.path.join(day_dir, filename)
        with open(filepath, "w") as f:
            f.write(content)
        logger.info("Report saved: %s", filepath)
        return filepath

    def cleanup(self) -> int:
        if not os.path.exists(self.base_dir):
            return 0
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        removed = 0
        for name in os.listdir(self.base_dir):
            dir_path = os.path.join(self.base_dir, name)
            if not os.path.isdir(dir_path):
                continue
            try:
                dir_date = datetime.strptime(name, "%Y-%m-%d")
                if dir_date < cutoff:
                    shutil.rmtree(dir_path)
                    logger.info("Cleaned up old reports: %s", name)
                    removed += 1
            except ValueError:
                continue
        return removed
