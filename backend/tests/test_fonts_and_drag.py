"""Cyrillic font coverage and draggable plate-text position regressions."""
import io
import unittest
import zipfile

import numpy as np
import trimesh
from PIL import ImageFont
from shapes.text_render import FONT_PATHS, text_geometry
from shapes.build import generate
from shapes.exporter import make_3mf
from shapes.schemas import GenerateRequest, PlateOptions


class FontAndPlacementTests(unittest.TestCase):
    def test_fonts_render_cyrillic(self):
        new_fonts = ("russo", "play", "pt-sans", "lobster",
                     "rubik-mono", "unbounded", "comfortaa", "terminus")
        for key in new_fonts:
            with self.subTest(font=key):
                font = ImageFont.truetype(str(FONT_PATHS[key]), 64)
                glyph = font.getmask("ЁЖ")
                self.assertGreater(glyph.getbbox()[2], 0)
                options = PlateOptions(text="КОТ", font=key,
                                       width_mm=140, height_mm=70, font_size_mm=8)
                preview = generate(GenerateRequest(kind="plate", plate=options))
                self.assertEqual(len(preview.parts), 2)
                self.assertIsNotNone(preview.text_bounds_mm)
                mesh = trimesh.Trimesh(vertices=np.array(preview.parts[1].vertices),
                                       faces=np.array(preview.parts[1].faces), process=False)
                self.assertTrue(mesh.is_watertight)
                self.assertGreater(mesh.volume, 0)

    def test_text_bounds_track_actual_drag_position(self):
        for style in ("raised", "inlay", "engraved"):
            with self.subTest(style=style):
                before = PlateOptions(text="МИР", width_mm=100, height_mm=50,
                                      text_style=style, text_x_mm=0, text_y_mm=0)
                after = before.model_copy(update={"text_x_mm":9,"text_y_mm":-6})
                a = generate(GenerateRequest(kind="plate", plate=before))
                b = generate(GenerateRequest(kind="plate", plate=after))
                self.assertEqual(len(a.text_bounds_mm), 4)
                self.assertEqual(len(b.text_bounds_mm), 4)
                for i in (0,2):
                    self.assertAlmostEqual(b.text_bounds_mm[i]-a.text_bounds_mm[i], 9, delta=0.01)
                for i in (1,3):
                    self.assertAlmostEqual(b.text_bounds_mm[i]-a.text_bounds_mm[i], -6, delta=0.01)
                self.assertAlmostEqual(b.text_surface_z, before.thickness_mm + (before.text_depth_mm if style=="raised" else 0))
                self.assertEqual(b.mount_surface_z, before.thickness_mm)
                self.assertIn("3D/3dmodel.model",
                              zipfile.ZipFile(io.BytesIO(make_3mf(b))).namelist())

    def test_drag_outside_rounded_plate_is_rejected(self):
        options = PlateOptions(text="МИР", width_mm=90, height_mm=38, text_x_mm=45)
        with self.assertRaisesRegex(ValueError, "границы основы"):
            generate(GenerateRequest(kind="plate", plate=options))


if __name__ == "__main__":
    unittest.main()
