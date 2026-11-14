"""Regression coverage for wizard's shared mounts, colored images and part caching."""
import base64
import io
import unittest
import zipfile
from xml.etree import ElementTree as ET

import numpy as np
import trimesh

from shapes.build import generate
from shapes.exporter import make_3mf
from shapes.geometry import _cached_extrusion
from shapes.image_trace import _trace_cached
from shapes.picture import optimized_picture
from shapes.picture_mesh import _image_regions
from shapes.schemas import (GenerateRequest,PlateOptions,SilhouetteOptions,
                            PictureSettings,MagnetSettings,MagnetPosition)

CORE="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
SVG='''<svg xmlns="http://www.w3.org/2000/svg" width="72" height="48">
<rect width="72" height="48" fill="#ee3322"/>
<rect width="36" height="48" fill="#2244bb"/>
</svg>'''
def sample():
    return "data:image/svg+xml;base64,"+base64.b64encode(SVG.encode()).decode()

def volume(part):
    mesh=trimesh.Trimesh(vertices=np.asarray(part.vertices),
                         faces=np.asarray(part.faces),process=False)
    assert mesh.is_watertight, part.name
    assert mesh.volume>0,part.name
    return mesh.volume

def plate(**kw):
    options=PlateOptions(**kw)
    return generate(GenerateRequest(kind="plate",plate=options))

def figure(**kw):
    options=SilhouetteOptions(image_data=sample(),**kw)
    return generate(GenerateRequest(kind="silhouette",silhouette=options))

class PictureMountTests(unittest.TestCase):
    def test_all_color_optimizers_with_manual_palette(self):
        for mode in ("nearest","median","kmeans","floyd"):
            with self.subTest(mode=mode):
                opts=PictureSettings(image_data=sample(),resolution=32,
                  color_count=2,algorithm=mode,filament_palette=["#1122AA","#DD3322"])
                indices,colors,url=optimized_picture(opts)
                self.assertEqual(set(colors),set(opts.filament_palette))
                self.assertEqual(len(colors),2)
                self.assertEqual(indices.ndim,2)
                self.assertTrue(url.startswith("data:image/png;base64,"))

    def test_picture_is_face_down_and_multicolor(self):
        picture=PictureSettings(image_data=sample(),resolution=24,width_mm=44,
                                layer_mm=0.4,color_count=2)
        result=plate(content_type="image",picture=picture,thickness_mm=3.2)
        self.assertEqual(len(result.image_palette),2)
        self.assertEqual(len([p for p in result.parts if "Изображение" in p.name]),2)
        self.assertIsNotNone(result.image_preview_url)
        for part in result.parts:
            volume(part)
            if "Изображение" in part.name:
                self.assertAlmostEqual(min(v[2] for v in part.vertices),0,delta=1e-5)
                self.assertAlmostEqual(max(v[2] for v in part.vertices),0.4,delta=1e-5)
        self.assertEqual(len(result.text_bounds_mm),4)

    def test_slicer_3mf_has_core_materials_and_descriptive_names(self):
        picture=PictureSettings(image_data=sample(),resolution=24,color_count=2)
        output=plate(content_type="image",picture=picture)
        with zipfile.ZipFile(io.BytesIO(make_3mf(output))) as z:
            root=ET.fromstring(z.read("3D/3dmodel.model"))
        mats=root.find(f".//{{{CORE}}}basematerials")
        self.assertIsNotNone(mats)
        colors=[m.attrib["displaycolor"][:7] for m in mats.findall(f"{{{CORE}}}base")]
        self.assertEqual(set(colors),{part.color for part in output.parts})
        items=root.findall(f".//{{{CORE}}}object")
        partobjs=[o for o in items if o.find(f"{{{CORE}}}mesh") is not None]
        self.assertEqual(len(partobjs),len(output.parts))
        for obj,part in zip(partobjs,output.parts):
            self.assertEqual(obj.attrib["name"],part.name)
            self.assertEqual(colors[int(obj.attrib["pindex"])],part.color)
            self.assertEqual(obj.attrib["pid"],"1")
        self.assertIsNone(root.find(".//{http://schemas.microsoft.com/3dmanufacturing/material/2015/02}basematerials"))

    def test_magnets_share_same_schema_between_figure_and_plate(self):
        magnets=MagnetSettings(shape="round",diameter_mm=6,depth_mm=1.8,
            positions=[MagnetPosition(x_mm=-12,y_mm=0),MagnetPosition(x_mm=12,y_mm=0)])
        for item in (
            figure(mount_type="magnets",magnets=magnets,thickness_mm=4),
            plate(text="AB",width_mm=90,height_mm=36,mount_type="magnets",
                  magnets=magnets,thickness_mm=4)):
            self.assertEqual(len(item.magnet_positions),2)
            self.assertEqual(item.magnet_surface_z,0)
            for part in item.parts:volume(part)

    def test_picture_magnet_pockets_open_on_back(self):
        picture=PictureSettings(image_data=sample(),resolution=24,color_count=2,layer_mm=0.4)
        magnets=MagnetSettings(depth_mm=1.2,
            positions=[MagnetPosition(x_mm=0,y_mm=0)])
        plain=plate(content_type="image",picture=picture,thickness_mm=3.2)
        carved=plate(content_type="image",picture=picture,thickness_mm=3.2,
                     mount_type="magnets",magnets=magnets)
        self.assertEqual(carved.magnet_surface_z,3.2)
        self.assertLess(sum(map(volume,carved.parts)),sum(map(volume,plain.parts)))
        for part in carved.parts: volume(part)

    def test_rectangular_magnets_and_invalid_positions(self):
        magnets=MagnetSettings(shape="rectangle",width_mm=11,height_mm=6,depth_mm=1.5,
            positions=[MagnetPosition(x_mm=8,y_mm=0)])
        result=plate(text="А",mount_type="magnets",magnets=magnets)
        for part in result.parts:volume(part)
        bad=magnets.model_copy(update={"positions":[MagnetPosition(x_mm=140,y_mm=0)]})
        with self.assertRaisesRegex(ValueError,"не помещается"):
            plate(text="А",mount_type="magnets",magnets=bad)

    def test_incremental_geometry_cache_survives_unrelated_text_change(self):
        _cached_extrusion.cache_clear()
        plate(text="КОЗА",font_size_mm=6)
        first=_cached_extrusion.cache_info()
        plate(text="КОТ",font_size_mm=6)
        second=_cached_extrusion.cache_info()
        self.assertGreater(second.hits,first.hits)

    def test_picture_polygons_not_recomputed_when_magnet_moves(self):
        picture=PictureSettings(image_data=sample(),resolution=24,color_count=2)
        _image_regions.cache_clear()
        plate(content_type="image",picture=picture,thickness_mm=4)
        hits=_image_regions.cache_info().hits
        mags=MagnetSettings(depth_mm=1.4,
              positions=[MagnetPosition(x_mm=5,y_mm=0)])
        plate(content_type="image",picture=picture,thickness_mm=4,
              mount_type="magnets",magnets=mags)
        self.assertGreater(_image_regions.cache_info().hits,hits)

    def test_trace_not_recomputed_when_mount_changes(self):
        _trace_cached.cache_clear()
        figure(attach_loop=False)
        hits=_trace_cached.cache_info().hits
        figure(mount_type="loop")
        self.assertGreater(_trace_cached.cache_info().hits,hits)

if __name__=="__main__":
    unittest.main()
