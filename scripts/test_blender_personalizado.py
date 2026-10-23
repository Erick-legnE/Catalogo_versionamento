import unittest
from pathlib import Path
from unittest import mock

from scripts.blender_personalizado import (
    automation_layer_settings,
    preview_curve_pose,
    preview_curve_vertex,
    rigid_curve_point,
)


class BlenderPersonalizadoTests(unittest.TestCase):
    def test_automation_text_coordinates_convert_to_button_millimetres(self):
        fixture = Path(__file__).with_name("fixtures") / "automation_text_request.json"
        result = automation_layer_settings(fixture, 1)

        millimetres_per_pixel = 32 / 518
        self.assertEqual(result["text"], "ANA")
        self.assertEqual(result["face"], "BACK")
        self.assertAlmostEqual(result["position_mm"][0], -50 * millimetres_per_pixel)
        self.assertAlmostEqual(result["position_mm"][1], 40 * millimetres_per_pixel)
        self.assertAlmostEqual(result["target_width_mm"], 210 * millimetres_per_pixel)
        self.assertAlmostEqual(result["target_height_mm"], 70 * millimetres_per_pixel)
        self.assertEqual(result["rotation_degrees"], -25)
        self.assertEqual(result["mode"], "ENGRAVE")
        self.assertEqual(result["depth_mm"], 0.5)
        self.assertEqual(result["curvature"], 0)

    def test_positive_curvature_raises_centre_and_lowers_ends(self):
        bounds = (0.0, 100.0, -10.0, 10.0)
        _x, centre_y = preview_curve_vertex(50.0, 0.0, bounds, 1.0)
        _x, left_y = preview_curve_vertex(0.0, 0.0, bounds, 1.0)
        _x, right_y = preview_curve_vertex(100.0, 0.0, bounds, 1.0)

        self.assertGreater(centre_y, 0)
        self.assertLess(left_y, 0)
        self.assertAlmostEqual(left_y, right_y)

    def test_negative_curvature_reverses_the_arc(self):
        bounds = (0.0, 100.0, -10.0, 10.0)
        _x, centre_y = preview_curve_vertex(50.0, 0.0, bounds, -0.75)
        _x, edge_y = preview_curve_vertex(0.0, 0.0, bounds, -0.75)

        self.assertLess(centre_y, 0)
        self.assertGreater(edge_y, 0)

    def test_rigid_glyph_curve_preserves_point_distance_from_pivot(self):
        bounds = (0.0, 100.0, -10.0, 10.0)
        offset, angle = preview_curve_pose(15.0, bounds, 0.9)
        original = (18.0, 6.0)
        pivot = (15.0, 1.0)
        curved = rigid_curve_point(*original, *pivot, offset, angle)

        before = ((original[0] - pivot[0]) ** 2 + (original[1] - pivot[1]) ** 2) ** 0.5
        after = ((curved[0] - pivot[0]) ** 2 + (curved[1] - (pivot[1] + offset)) ** 2) ** 0.5
        self.assertAlmostEqual(before, after)

    def test_uploaded_font_is_resolved_only_from_the_request_package(self):
        request_path = Path(__file__).with_name("fixtures") / "automation_text_uploaded_font_request.json"
        with mock.patch.object(Path, "is_file", return_value=True):
            result = automation_layer_settings(request_path, 1)

        self.assertEqual(result["font_source"], "uploaded")
        self.assertEqual(result["font_path"], str(request_path.with_name("fonte_personalizacao.ttf")))
        self.assertEqual(result["font_sha256"], "abc123")
        self.assertAlmostEqual(result["pastilha_back_face_recess_mm"], 0.2)


if __name__ == "__main__":
    unittest.main()
