import csv
import unittest
from pathlib import Path

try:
    from scripts.blender_button import load_geometry
    from scripts.consistem_sync import sync_once
except ModuleNotFoundError:
    from blender_button import load_geometry
    from consistem_sync import sync_once


class PlannerWorkTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]

    def test_consistem_sync_deduplicates_rows(self):
        folder = self.root / "outputs"
        source = folder / "_test_consistem_export.csv"
        output = folder / "_test_consistem_sync.csv"
        try:
            source.write_text("reduzido;descricao\nA1;primeiro\nA2;segundo\n", encoding="utf-8")
            self.assertEqual(sync_once(source, output)["total"], 2)
            self.assertEqual(sync_once(source, output)["total"], 2)
            with output.open(encoding="utf-8", newline="") as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 2)
        finally:
            for path in (source, output, folder / "sync_report.json"):
                path.unlink(missing_ok=True)

    def test_button_geometry_uses_reference_hole_data(self):
        geometry = load_geometry("16", 18, self.root / "docs/data")
        self.assertEqual(geometry["hole_count"], 4)
        self.assertEqual(len(geometry["points_mm"]), 4)
        self.assertGreater(geometry["thickness_mm"], 0)


if __name__ == "__main__":
    unittest.main()
