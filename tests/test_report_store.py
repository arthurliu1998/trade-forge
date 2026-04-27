import os
from datetime import datetime
from quantforge.monitor.report_store import ReportStore


class TestReportStore:
    def test_save_creates_date_directory(self, tmp_path):
        store = ReportStore(base_dir=str(tmp_path))
        store.save("signal", "NVDA", "# Report content")
        today = datetime.now().strftime("%Y-%m-%d")
        assert (tmp_path / today).is_dir()

    def test_save_creates_markdown_file(self, tmp_path):
        store = ReportStore(base_dir=str(tmp_path))
        path = store.save("signal", "NVDA", "# Report content")
        assert path.endswith(".md")
        assert os.path.exists(path)
        with open(path) as f:
            assert f.read() == "# Report content"

    def test_save_filename_contains_symbol_and_type(self, tmp_path):
        store = ReportStore(base_dir=str(tmp_path))
        path = store.save("signal", "NVDA", "content")
        filename = os.path.basename(path)
        assert "NVDA" in filename
        assert "signal" in filename

    def test_save_briefing_no_symbol(self, tmp_path):
        store = ReportStore(base_dir=str(tmp_path))
        path = store.save("briefing", "tw-premarket", "# Briefing")
        filename = os.path.basename(path)
        assert "briefing" in filename
        assert "tw-premarket" in filename

    def test_cleanup_removes_old_directories(self, tmp_path):
        store = ReportStore(base_dir=str(tmp_path), retention_days=0)
        old_dir = tmp_path / "2020-01-01"
        old_dir.mkdir()
        (old_dir / "report.md").write_text("old")
        store.cleanup()
        assert not old_dir.exists()

    def test_cleanup_keeps_recent_directories(self, tmp_path):
        store = ReportStore(base_dir=str(tmp_path), retention_days=30)
        today = datetime.now().strftime("%Y-%m-%d")
        today_dir = tmp_path / today
        today_dir.mkdir()
        (today_dir / "report.md").write_text("recent")
        store.cleanup()
        assert today_dir.exists()
