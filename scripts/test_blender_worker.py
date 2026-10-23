import json
import unittest
from pathlib import Path

from scripts.blender_worker import build_plan, process, resolve_base_blend, text_layers, validate_blender_outputs


class BlenderWorkerTests(unittest.TestCase):
    def test_text_layers_ignores_images_and_empty_text(self):
        metadata = {"personalization": {"assets": [
            {"layer": 1, "kind": "text", "text": "ANA"},
            {"layer": 2, "kind": "image", "text": ""},
            {"layer": 3, "kind": "text", "text": ""},
            {"layer": 4, "kind": "text", "text": "LIA"},
        ]}}
        self.assertEqual(text_layers(metadata), [1, 4])

    def test_base_resolution_uses_reference_and_size_filename(self):
        base_dir = Path(__file__).resolve().parents[1] / "versions" / "engraving-matrix-2026-10-21" / "bases"
        metadata = {"item": {"reference": "13648", "size_tam": 18}}
        self.assertEqual(resolve_base_blend(metadata, base_dir).name, "button_13648_18.blend")

    def test_success_requires_blend_report_render_and_changed_manifold_mesh(self):
        root = Path(__file__).resolve().parents[1] / "versions" / "engraving-matrix-2026-10-21" / "personalized"
        report = root / "ref_13646_tam_18_lia.json"
        output = root / "ref_13646_tam_18_lia.blend"
        render = root / "ref_13646_tam_18_lia.png"
        result = validate_blender_outputs(output, report, render)
        diagnostics = result["geometry_diagnostics"]
        self.assertGreater(diagnostics["body_vertices_after"], diagnostics["body_vertices_before"])
        self.assertEqual(diagnostics["boundary_edges"], 0)
        self.assertEqual(diagnostics["non_manifold_edges"], 0)


if __name__ == "__main__":
    unittest.main()
