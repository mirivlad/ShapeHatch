"""Regression tests for enclosed line-art regions and rounded top perimeters."""
import base64
import io
import unittest
import zipfile
from xml.etree import ElementTree as ET

import numpy as np
import trimesh

from shapes.build import generate
from shapes.exporter import make_3mf, make_stl, make_stl_zip
from shapes.schemas import GenerateRequest, InnerContourOption, PlateOptions, SilhouetteOptions


def svg_url(svg):
    return "data:image/svg+xml;base64,"+base64.b64encode(svg.encode()).decode()


# A thin outer border and an independent closed heart, like scanned goat artwork.
LINE_ART = svg_url("""<svg xmlns="http://www.w3.org/2000/svg" width="180" height="130">
<rect x="10" y="10" width="160" height="110" fill="none" stroke="black" stroke-width="3"/>
<path d="M78 60 C63 39 40 54 54 72 L78 96 L102 72 C116 54 93 39 78 60Z"
 fill="none" stroke="black" stroke-width="3"/>
</svg>""")

CUTOUT = svg_url("""<svg xmlns="http://www.w3.org/2000/svg" width="150" height="120">
<path d="M10 10 H140 V110 H10 Z M60 42 H91 V75 H60 Z" fill="black" fill-rule="evenodd"/>
</svg>""")


def mesh(part):
    return trimesh.Trimesh(vertices=np.asarray(part.vertices),
                           faces=np.asarray(part.faces), process=False)


def model(url, mode="filled", setting=None, round_mm=0.3):
    opts=SilhouetteOptions(image_data=url, mode=mode, attach_loop=False,
                           width_mm=65, top_round_mm=round_mm,
                           inner_contours=[setting] if setting else [])
    return generate(GenerateRequest(kind="silhouette", silhouette=opts))


class InnerContourTests(unittest.TestCase):
    def assert_solid(self, generated):
        for part in generated.parts:
            self.assertTrue(mesh(part).is_watertight, part.name)
            self.assertGreater(mesh(part).volume, 0, part.name)

    def test_closed_heart_inside_outline_is_editable(self):
        generated=model(LINE_ART)
        self.assert_solid(generated)
        self.assertEqual(len(generated.inner_contours), 1)
        self.assertEqual(generated.inner_contours[0].id, "inner-1")
        self.assertGreater(len(generated.inner_contours[0].points), 6)

    def test_same_empty_or_other_material(self):
        original=model(LINE_ART)
        hollow=model(LINE_ART, setting=InnerContourOption(id="inner-1",fill="empty"))
        colored=model(LINE_ART, setting=InnerContourOption(
            id="inner-1", fill="other", color="#FF6600"))
        for result in (original,hollow,colored):
            self.assert_solid(result)
            self.assertEqual(len(result.inner_contours),1)
        self.assertLess(sum(mesh(x).volume for x in hollow.parts),
                        sum(mesh(x).volume for x in original.parts))
        self.assertEqual(len(colored.parts), 3)
        self.assertEqual(colored.parts[-1].color, "#FF6600")
        self.assertAlmostEqual(sum(mesh(x).volume for x in colored.parts),
                               sum(mesh(x).volume for x in original.parts), delta=1.0)
        with zipfile.ZipFile(io.BytesIO(make_3mf(colored))) as archive:
            xml=archive.read("3D/3dmodel.model")
            self.assertIn(b"#FF6600",xml)
        self.assertGreater(len(make_stl(colored)),100)
        with zipfile.ZipFile(io.BytesIO(make_stl_zip(colored))) as archive:
            self.assertEqual(len([x for x in archive.namelist() if x.endswith(".stl")]),3)

    def test_line_art_cutouts_preserves_outer_body(self):
        # A one-pixel border has a >90% white central area. It must not
        # become a giant hole just because the user chose cutouts.
        thin = svg_url("""<svg xmlns="http://www.w3.org/2000/svg" width="180" height="130">
        <rect x="10" y="10" width="160" height="110"
         fill="none" stroke="black" stroke-width="1"/>
        <path d="M78 60 C63 39 40 54 54 72 L78 96 L102 72 C116 54 93 39 78 60Z"
         fill="none" stroke="black" stroke-width="1"/>
        </svg>""")
        base = model(thin, mode="filled")
        punched = model(thin, mode="cutouts")
        self.assert_solid(base)
        self.assert_solid(punched)
        self.assertEqual(len(punched.inner_contours), 1)
        self.assertEqual(punched.inner_contours[0].fill, "empty")
        # Heart is a small detail; don't remove 95% of the model.
        self.assertGreater(mesh(punched.parts[0]).volume,
                           mesh(base.parts[0]).volume * 0.7)

    def test_filled_image_cutout_is_detected_even_when_filled(self):
        model_filled=model(CUTOUT)
        model_cutouts=model(CUTOUT,mode="cutouts")
        self.assert_solid(model_filled)
        self.assert_solid(model_cutouts)
        self.assertEqual(len(model_filled.inner_contours),1)
        self.assertEqual(len(model_cutouts.inner_contours),1)
        self.assertEqual(model_filled.inner_contours[0].fill,"same")
        self.assertEqual(model_cutouts.inner_contours[0].fill,"empty")
        self.assertGreater(mesh(model_filled.parts[0]).volume,
                           mesh(model_cutouts.parts[0]).volume)

    def test_color_insert_with_both_mount_orientations(self):
        for orientation in ("flat", "upright"):
            with self.subTest(orientation=orientation):
                opts = SilhouetteOptions(
                    image_data=LINE_ART, loop_orientation=orientation,
                    inner_contours=[InnerContourOption(
                        id="inner-1", fill="other", color="#46A3FF")])
                generated = generate(GenerateRequest(kind="silhouette",
                                                    silhouette=opts))
                self.assert_solid(generated)
                self.assertEqual(len(generated.parts), 3)
                self.assertEqual(generated.parts[-1].color, "#46A3FF")

    def test_top_radius_0_2_0_4_preserves_printable_mesh(self):
        for radius in (0.0,0.2,0.3,0.4):
            with self.subTest(radius=radius):
                result=model(LINE_ART,round_mm=radius)
                self.assert_solid(result)
                self.assertAlmostEqual(max(v[2] for v in result.parts[0].vertices),3,delta=1e-5)
        no_round=model(LINE_ART,round_mm=0)
        rounded=model(LINE_ART,round_mm=0.4)
        self.assertLess(mesh(rounded.parts[0]).volume,mesh(no_round.parts[0]).volume)

    def test_plate_and_inlay_rounded_and_sharp(self):
        for style in ("raised","inlay","engraved"):
            opts=PlateOptions(text="AB", text_style=style,top_round_mm=0.4)
            result=generate(GenerateRequest(kind="plate",plate=opts))
            self.assert_solid(result)
            self.assertEqual(len(result.parts),3 if style=="inlay" else 2)
        for radius in (0.0,0.3):
            plate=generate(GenerateRequest(kind="plate", plate=PlateOptions(
                text="A",shape="rectangle",top_round_mm=radius)))
            self.assert_solid(plate)
            top=[v for v in plate.parts[0].vertices if abs(v[2]-3)<1e-5]
            self.assertTrue(top)
            self.assertAlmostEqual(max(v[0] for v in top),
                                   40-radius,delta=0.02)


if __name__=="__main__":
    unittest.main()
