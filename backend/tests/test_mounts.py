"""Regression tests for contour-snap mounts and upright manifold unions."""
import base64
import io
import unittest
import zipfile

import numpy as np
import trimesh
from shapely.geometry import Point, box
from shapely.ops import unary_union

from shapes.build import generate
from shapes.mounts import contour_samples, mount_placement, primary_outline
from shapes.exporter import make_3mf, make_stl, make_stl_zip
from shapes.schemas import GenerateRequest, PlateOptions, SilhouetteOptions


def svg_url(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


SAMPLE = svg_url('<svg xmlns="http://www.w3.org/2000/svg" width="140" height="100">'
                 '<path d="M10 10 H130 V90 H10 Z" fill="black"/></svg>')


class MountsTests(unittest.TestCase):
    def assert_solid(self, part):
        mesh = trimesh.Trimesh(vertices=np.array(part.vertices),
                               faces=np.array(part.faces), process=False)
        self.assertTrue(mesh.is_watertight, part.name)
        self.assertGreater(mesh.volume, 0, part.name)
        return mesh

    def test_perimeter_snap_uses_real_outer_contour(self):
        # Choose the larger island, not an interior hole or a detached fragment.
        large = box(-40, -20, 40, 20).difference(Point(0, 0).buffer(6))
        shape = unary_union([large, box(60, 40, 62, 42)])
        line = primary_outline(shape)
        self.assertAlmostEqual(line.length, 240, delta=0.01)
        points = contour_samples(line)
        self.assertEqual(len(points), 385)
        self.assertEqual(points[0], points[-1])
        for fraction in (0, 0.125, 0.5, 0.875):
            anchor, outward, tangent, actual = mount_placement(line, fraction, "top", 0.5)
            self.assertAlmostEqual(actual, fraction, delta=1e-8)
            self.assertLess(anchor.distance(line), 1e-8)
            self.assertAlmostEqual(np.dot(outward, tangent), 0, delta=1e-7)

    def test_flat_and_upright_eyelid_plate_forms(self):
        for form in ("rounded", "rectangle", "oval", "circle", "hexagon"):
            for style in ("loop", "upright"):
                for fraction in (0.07, 0.27, 0.56, 0.83):
                    with self.subTest(form=form, style=style, fraction=fraction):
                        plate = PlateOptions(text="А", width_mm=90, height_mm=60,
                                             shape=form, mount_type=style,
                                             mount_contour_t=fraction)
                        result = generate(GenerateRequest(kind="plate", plate=plate))
                        self.assert_solid(result.parts[0])
                        self.assertEqual(len(result.mount_contour), 385)
                        self.assertAlmostEqual(result.mount_fraction, fraction)
                        expected_thickness = (
                            plate.mount_hole_mm + 2 * plate.mount_wall_mm
                            if style == "upright" else plate.thickness_mm)
                        self.assertAlmostEqual(result.mount_surface_z, expected_thickness)
                        if style == "upright":
                            body = self.assert_solid(result.parts[0])
                            self.assertEqual(body.euler_number, 0)  # one transverse hole
                            self.assertAlmostEqual(body.bounds[0, 2], 0, delta=0.001)
                            self.assertAlmostEqual(body.bounds[1, 2], expected_thickness, delta=0.001)
                            self.assertAlmostEqual(result.size_mm[2],
                                                   expected_thickness + plate.text_depth_mm,
                                                   delta=0.05)

    def test_inlay_engraving_and_raised_upright(self):
        for text_style in ("raised", "inlay", "engraved"):
            for position in (0.25, 0.50):
                with self.subTest(style=text_style, position=position):
                    plate = PlateOptions(text="КОЗА\n2026", width_mm=100, height_mm=55,
                                         font_size_mm=7, mount_type="upright",
                                         mount_contour_t=position, text_style=text_style)
                    preview = generate(GenerateRequest(kind="plate", plate=plate))
                    for part in preview.parts:
                        self.assert_solid(part)
                    self.assertEqual(len(preview.parts), 2 if text_style != "engraved" else 1)
                    archive = zipfile.ZipFile(io.BytesIO(make_3mf(preview)))
                    self.assertIn("3D/3dmodel.model", archive.namelist())
                    self.assertGreater(len(make_stl(preview)), 100)
                    self.assertIn("README.txt", zipfile.ZipFile(io.BytesIO(make_stl_zip(preview))).namelist())

    def test_silhouette_legacy_and_drag_positions(self):
        for orientation in ("flat", "upright"):
            for position in (None, 0.08, 0.4, 0.7):
                with self.subTest(orientation=orientation, position=position):
                    opts = SilhouetteOptions(image_data=SAMPLE,
                                             loop_orientation=orientation,
                                             loop_contour_t=position)
                    preview = generate(GenerateRequest(kind="silhouette", silhouette=opts))
                    self.assert_solid(preview.parts[0])
                    self.assertEqual(len(preview.mount_contour), 385)
                    self.assertIsNotNone(preview.mount_fraction)
                    if position is not None:
                        self.assertAlmostEqual(preview.mount_fraction, position)
                    if orientation == "upright":
                        expected_thickness = opts.loop_hole_mm + 2 * opts.loop_wall_mm
                        self.assertAlmostEqual(preview.size_mm[2], expected_thickness,
                                               delta=0.001)
                        self.assertEqual(self.assert_solid(preview.parts[0]).euler_number, 0)

    def test_post_is_edge_mounted_and_flush_with_both_faces(self):
        plate = PlateOptions(text="А", shape="rectangle", width_mm=80, height_mm=36,
                             thickness_mm=2.5, mount_type="upright", mount_side="top",
                             mount_position=0.5, mount_hole_mm=5, mount_wall_mm=2.3)
        result = generate(GenerateRequest(kind="plate", plate=plate))
        body = self.assert_solid(result.parts[0])
        nominal_diameter = plate.mount_hole_mm + 2 * plate.mount_wall_mm
        self.assertAlmostEqual(body.bounds[0, 2], 0, delta=0.001)
        self.assertAlmostEqual(body.bounds[1, 2], nominal_diameter, delta=0.001)
        self.assertAlmostEqual(result.mount_surface_z, nominal_diameter)
        self.assertGreater(body.bounds[1, 1], plate.height_mm / 2 + nominal_diameter * 0.9)
        self.assertEqual(body.euler_number, 0)

    def test_post_handles_corners_and_different_diameters(self):
        for shape in ("rounded", "rectangle", "hexagon"):
            for fraction in (0, 0.001, 0.5, 0.999, 1):
                for hole, wall in ((3, 1.4), (5, 2.3)):
                    with self.subTest(shape=shape, fraction=fraction, hole=hole):
                        opts = PlateOptions(text="А", shape=shape, mount_type="upright",
                                            mount_contour_t=fraction,
                                            mount_hole_mm=hole, mount_wall_mm=wall)
                        result = generate(GenerateRequest(kind="plate", plate=opts))
                        base = self.assert_solid(result.parts[0])
                        self.assertEqual(base.euler_number, 0)
                        self.assertAlmostEqual(base.bounds[1, 2], hole + 2 * wall,
                                               delta=0.001)

    def test_mount_off_and_legacy_hole(self):
        plain = generate(GenerateRequest(kind="plate", plate=PlateOptions(text="А")))
        self.assertIsNone(plain.mount_fraction)
        self.assertTrue(plain.mount_contour)
        holed = generate(GenerateRequest(kind="plate", plate=PlateOptions(
            text="А", mount_type="hole", mount_side="left", mount_position=0.5)))
        self.assert_solid(holed.parts[0])
        self.assertIsNotNone(holed.mount_fraction)


if __name__ == "__main__":
    unittest.main()
