import base64
import io
import unittest
import zipfile
from xml.etree import ElementTree as ET

import numpy as np
import trimesh
from shapes.build import generate
from shapes.exporter import make_3mf, make_stl_zip
from shapes.schemas import GenerateRequest, PlateOptions, SilhouetteOptions


def svg_url(text: str):
    return "data:image/svg+xml;base64," + base64.b64encode(text.encode()).decode()


SAMPLE = svg_url('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="90" viewBox="0 0 100 90">'
                 '<path d="M10 10 H90 V75 H10 Z" fill="black"/></svg>')


class ShapeHatchModels(unittest.TestCase):
    def assert_meshes(self, model):
        self.assertTrue(model.parts)
        for part in model.parts:
            mesh = trimesh.Trimesh(vertices=np.array(part.vertices),
                                  faces=np.array(part.faces), process=False)
            self.assertTrue(mesh.is_watertight, part.name)
            self.assertGreater(mesh.volume, 0, part.name)

    def test_flat_silhouette_with_loop(self):
        result = generate(GenerateRequest(kind="silhouette", silhouette=SilhouetteOptions(
            image_data=SAMPLE, width_mm=55, attach_loop=True)))
        self.assert_meshes(result)
        self.assertGreater(result.size_mm[0], 50)
        self.assertGreater(result.size_mm[1], 30)

    def test_silhouette_without_loop(self):
        result = generate(GenerateRequest(kind="silhouette", silhouette=SilhouetteOptions(
            image_data=SAMPLE, attach_loop=False)))
        self.assert_meshes(result)
        self.assertAlmostEqual(result.size_mm[0], 55.0, delta=0.1)

    def test_raised_plate_with_cyrillic(self):
        result = generate(GenerateRequest(kind="plate", plate=PlateOptions(text="КОЗА")))
        self.assert_meshes(result)
        self.assertEqual(len(result.parts), 2)
        self.assertEqual(result.parts[1].color, "#F8FBFA")

    def test_multiline_plate_with_cyrillic(self):
        options = PlateOptions(text="КОЗА\n2026", width_mm=90, height_mm=42,
                               text_align="center", line_spacing_mm=2)
        model = generate(GenerateRequest(kind="plate", plate=options))
        self.assert_meshes(model)
        self.assertEqual(len(model.parts), 2)
        text_vertices = np.array(model.parts[1].vertices)
        self.assertGreater(np.ptp(text_vertices[:, 1]), 13)
        with zipfile.ZipFile(io.BytesIO(make_3mf(model))) as archive:
            self.assertIn("3D/3dmodel.model", archive.namelist())

    def test_multiline_inlay_and_alignment(self):
        for align in ("left", "center", "right"):
            with self.subTest(align=align):
                plate = PlateOptions(text="МАЛЫШ\n2026",
                                     width_mm=100, height_mm=44, text_style="inlay",
                                     font_size_mm=8, text_align=align,
                                     line_spacing_mm=1)
                result = generate(GenerateRequest(kind="plate", plate=plate))
                self.assert_meshes(result)
                self.assertEqual(len(result.parts), 3)

    def test_whitespace_only_multiline_text_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "непустую"):
            generate(GenerateRequest(kind="plate", plate=PlateOptions(text="\n  ")))

    def test_plate_mounts_on_each_shape(self):
        for shape in ("rounded", "rectangle", "oval", "circle", "hexagon"):
            for attachment in ("hole", "loop"):
                with self.subTest(shape=shape, mount=attachment):
                    plate = PlateOptions(text="А", width_mm=90, height_mm=54,
                                         shape=shape, mount_type=attachment,
                                         mount_side="top", mount_position=0.5)
                    result = generate(GenerateRequest(kind="plate", plate=plate))
                    self.assert_meshes(result)
                    self.assertEqual(len(result.parts), 2)
                    base = result.parts[0]
                    self.assertAlmostEqual(
                        min(v[2] for v in base.vertices), 0, delta=1e-5)
                    self.assertAlmostEqual(
                        max(v[2] for v in base.vertices), plate.thickness_mm, delta=1e-5)

    def test_plate_mounts_are_printable_with_all_text_styles(self):
        for style in ("raised", "inlay", "engraved"):
            for attachment in ("hole", "loop"):
                with self.subTest(style=style, mount=attachment):
                    options = PlateOptions(
                        text="А\nБ", width_mm=85, height_mm=48,
                        text_style=style, mount_type=attachment,
                        mount_side="left", mount_position=0.5)
                    result = generate(GenerateRequest(kind="plate", plate=options))
                    self.assert_meshes(result)
                    self.assertEqual(len(result.parts), 3 if style == "inlay" else 2)
                    with zipfile.ZipFile(io.BytesIO(make_3mf(result))) as archive:
                        self.assertIn("3D/3dmodel.model", archive.namelist())

    def test_plate_mount_changes_geometry(self):
        bare = PlateOptions(text="А", width_mm=90, height_mm=40)
        mounted = bare.model_copy(update={"mount_type": "loop"})
        holed = bare.model_copy(update={"mount_type": "hole"})
        def base_volume(options):
            part = generate(GenerateRequest(kind="plate", plate=options)).parts[0]
            return trimesh.Trimesh(vertices=part.vertices, faces=part.faces,
                                   process=False).volume
        self.assertGreater(base_volume(mounted), base_volume(bare))
        self.assertLess(base_volume(holed), base_volume(bare))

    def test_plate_hole_rejects_impossible_dimensions(self):
        options = PlateOptions(text="А", width_mm=90, height_mm=12,
                               mount_type="hole", mount_hole_mm=12,
                               mount_wall_mm=6)
        with self.assertRaisesRegex(ValueError, "Отверстие не помещается"):
            generate(GenerateRequest(kind="plate", plate=options))

    def test_inlay(self):
        result = generate(GenerateRequest(kind="plate", plate=PlateOptions(
            text="АННА", text_style="inlay")))
        self.assert_meshes(result)
        self.assertEqual(len(result.parts), 3)
        self.assertEqual(result.parts[0].color, result.parts[1].color)

    def test_svg_zip(self):
        result = generate(GenerateRequest(kind="plate", plate=PlateOptions(text="AB")))
        data = make_3mf(result)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = set(z.namelist())
            self.assertIn("3D/3dmodel.model", names)
            root = ET.fromstring(z.read("3D/3dmodel.model"))
            self.assertEqual(root.attrib["unit"], "millimeter")
            ns = {"c": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02",
                  "m": "http://schemas.microsoft.com/3dmanufacturing/material/2015/02"}
            self.assertEqual(len(root.findall(".//m:base", ns)), 2)
            self.assertEqual(len(root.findall(".//c:build/c:item", ns)), 1)
        with zipfile.ZipFile(io.BytesIO(make_stl_zip(result))) as z:
            self.assertEqual(len([p for p in z.namelist() if p.endswith(".stl")]), 2)


if __name__ == "__main__":
    unittest.main()
