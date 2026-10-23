import csv
import unittest
from pathlib import Path

try:
    from scripts.blender_button import load_geometry
    from scripts.consistem_sync import sync_once
    from scripts.consistem_blender_runner import configure_texture, number, validate_row
    from scripts.ficha_consistency import compare_item, expected_item
except ModuleNotFoundError:
    from blender_button import load_geometry
    from consistem_sync import sync_once
    from consistem_blender_runner import configure_texture, number, validate_row
    from ficha_consistency import compare_item, expected_item


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

    def test_consistem_numbers_preserve_decimal_floats(self):
        self.assertEqual(number(3.2), 3.2)
        self.assertEqual(number(" 3,2 "), 3.2)

    def test_texture_configuration_is_staged_without_windows_path_errors(self):
        source = "COLOR_CODE = 'OLD'\nFRONT_IMAGE_PATH = r''\nVERSO_IMAGE_PATH = r''\nSIDE_IMAGE_PATH = r''\nDEBUG_MODE = 'PHOTO'\nOUTPUT_BLEND_PATH = r''\nOUTPUT_REPORT_PATH = r''\n"
        result = configure_texture(
            source,
            "C2622",
            Path(r"C:\Fotos\front.png"),
            Path(r"C:\Fotos\verso.png"),
            Path(r"C:\Fotos\side.png"),
            Path(r"C:\Out\textured.blend"),
            Path(r"C:\Out\report.json"),
            "MARBLE_3D",
        )
        compile(result, "staged_texture.py", "exec")
        self.assertIn("C2622", result)
        self.assertIn("MARBLE_3D", result)

    def test_consistem_row_preflight_rejects_incomplete_hole_data(self):
        valid = validate_row({
            "descricao_produto": "BOTAO BAS 13646 4F TAM 18",
            "espessura_final": "3,2",
            "num_furos": "4",
            "broca": "1,8",
            "distancia_furos": "5,6",
            "faca_frente": "OP90",
        })
        self.assertEqual(valid["hole_radius_mm"], 0.9)
        with self.assertRaises(SystemExit):
            validate_row({
                "descricao_produto": "BOTAO BAS 13646 4F TAM 18",
                "espessura_final": "3,2",
                "num_furos": "4",
                "broca": "",
                "distancia_furos": "5,6",
                "faca_frente": "OP90",
            })

    def test_ficha_consistency_detects_a_wrong_final_thickness(self):
        expected = expected_item({
            "reference": "13646",
            "size": 18,
            "expected_geometry": {"diameter_mm": 18, "thickness_mm": 3.2, "hole_count": 4},
            "row": {"broca": "1,8", "distancia_furos": "5,6", "faca_frente": "OP90", "fundo": "390", "acabamento": "FOSCO"},
        })
        self.assertEqual(compare_item({**expected, "espessura_final_mm": 3.2}, expected), [])
        issues = compare_item({**expected, "espessura_final_mm": 2.2}, expected)
        self.assertEqual(issues[0]["field"], "espessura_final_mm")


if __name__ == "__main__":
    unittest.main()
