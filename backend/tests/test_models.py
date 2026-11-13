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
