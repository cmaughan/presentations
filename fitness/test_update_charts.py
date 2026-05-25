from pathlib import Path
import tempfile
import unittest

import update_charts


class UpdateChartsTests(unittest.TestCase):
    def test_copy_charts_copies_all_expected_pngs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            target = Path(temp_dir) / "target"
            source.mkdir()
            for filename in update_charts.CHART_FILES:
                (source / filename).write_bytes(b"png")

            copied = update_charts.copy_charts(source, target)

            self.assertEqual([path.name for path in copied], list(update_charts.CHART_FILES))
            for filename in update_charts.CHART_FILES:
                self.assertEqual((target / filename).read_bytes(), b"png")

    def test_copy_charts_reports_missing_chart(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(FileNotFoundError):
                update_charts.copy_charts(Path(temp_dir), Path(temp_dir) / "target")


if __name__ == "__main__":
    unittest.main()
