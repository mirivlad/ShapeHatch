"""Regression coverage for wizard's shared mounts, colored images and part caching."""
import base64
import io
from PIL import Image, ImageDraw
import unittest
import zipfile
from xml.etree import ElementTree as ET

import numpy as np
import trimesh

from shapes.build import generate
from shapes.exporter import make_3mf
from shapes.geometry import _cached_extrusion
from shapes.image_trace import _trace_cached
from shapes.picture import optimized_picture, _quantize
from shapes.picture_mesh import _image_regions, placement_dimensions
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

    def test_flat_four_color_logo_is_not_requantized(self):
        # A real 4-color logo must not drift just because K-Means or
        # Median Cut was selected. The exact RGB pixels are the ground truth.
        colors=np.asarray([[255,255,255],[0,0,0],[229,13,30],[30,90,170]],dtype=np.uint8)
        image=np.empty((48,72,3),dtype=np.uint8)
        for x in range(72):image[:,x]=colors[x//18]
        data=io.BytesIO()
        Image.fromarray(image).save(data,format="PNG")
        url="data:image/png;base64,"+base64.b64encode(data.getvalue()).decode()
        for method in ("auto","original","median","kmeans","nearest"):
            with self.subTest(method=method):
                opts=PictureSettings(image_data=url,algorithm=method,
                                     color_count=4,resolution=160,image_kind="logo")
                indexed,output_colors,_=optimized_picture(opts)
                rebuild=np.asarray([tuple(int(c[i:i+2],16) for i in (1,3,5))
                                    for c in output_colors],dtype=np.uint8)[indexed]
                self.assertTrue(np.array_equal(rebuild,image))
                self.assertEqual(set(output_colors),{"#FFFFFF","#000000","#E50D1E","#1E5AAA"})

    def test_approximate_jpeg_logo_keeps_white_black_red(self):
        image=np.full((100,160,3),255,dtype=np.uint8)
        image[20:82,27:130]=[234,15,28]
        image[28:35,36:122]=[0,0,0]
        buf=io.BytesIO()
        Image.fromarray(image).save(buf,format="JPEG",quality=90)
        url="data:image/jpeg;base64,"+base64.b64encode(buf.getvalue()).decode()
        opts=PictureSettings(image_data=url,algorithm="auto",color_count=4,
                             resolution=160,image_kind="logo")
        indexed,palette,_=optimized_picture(opts)
        rgb=np.array([tuple(int(c[i:i+2],16) for i in (1,3,5)) for c in palette])
        self.assertTrue(any((p>235).all() for p in rgb),palette)
        self.assertTrue(any((p<40).all() for p in rgb),palette)
        self.assertTrue(any(p[0]>170 and p[1]<60 and p[2]<70 for p in rgb),palette)
        self.assertLessEqual(len(palette),4)

    def test_dithering_is_separate_from_palette_algorithm(self):
        ramp=np.zeros((64,128,3),dtype=np.uint8)
        ramp[:]=np.linspace(0,255,128,dtype=np.uint8)[None,:,None]
        out=io.BytesIO()
        Image.fromarray(ramp).save(out,format="PNG")
        url="data:image/png;base64,"+base64.b64encode(out.getvalue()).decode()
        masks={}
        for mode in ("none","floyd","atkinson","bayer"):
            opts=PictureSettings(image_data=url,color_count=2,resolution=128,
                     algorithm="median",image_kind="photo",dithering=mode)
            masks[mode]=optimized_picture(opts)[0]
        self.assertFalse(np.array_equal(masks["none"],masks["floyd"]))
        self.assertFalse(np.array_equal(masks["none"],masks["atkinson"]))
        self.assertFalse(np.array_equal(masks["none"],masks["bayer"]))

    def test_plate_size_controls_image_and_cover_clips(self):
        from shapes.geometry import plate_shape
        from shapes.schemas import PlateOptions
        plate_options=PlateOptions(width_mm=90,height_mm=40,shape="rectangle")
        shape=plate_shape(plate_options)
        opts=PictureSettings(image_data=sample(),resolution=24)
        a=placement_dimensions(opts,shape,72,48)
        self.assertAlmostEqual(a[1],38.4,places=2)
        self.assertAlmostEqual(a[0],57.6,places=2)
        b=placement_dimensions(opts.model_copy(update={"fit_mode":"fill"}),shape,72,48)
        self.assertGreater(b[1],a[1])
        c=placement_dimensions(opts.model_copy(update={"fit_mode":"width"}),shape,72,48)
        self.assertAlmostEqual(c[0],88.4,places=2)
        d=placement_dimensions(opts.model_copy(update={"fit_mode":"manual","width_mm":20,"scale":1.5}),shape,72,48)
        self.assertAlmostEqual(d[0],30,places=3)
        fit=plate(content_type="image",width_mm=90,height_mm=40,shape="rectangle",
                  picture=opts)
        cover=plate(content_type="image",width_mm=90,height_mm=40,shape="rectangle",
                    picture=opts.model_copy(update={"fit_mode":"fill"}))
        self.assertEqual(len(fit.image_palette),2)
        self.assertEqual(len(cover.image_palette),2)
        for result in (fit,cover):
            for part in result.parts:
                volume(part)
                self.assertLessEqual(max(v[0] for v in part.vertices),45.001)
                self.assertGreaterEqual(min(v[0] for v in part.vertices),-45.001)

    def test_shape_is_visible_before_picture_is_uploaded(self):
        preview=plate(content_type="image",picture=PictureSettings())
        self.assertEqual(preview.parts[0].name,"Основа")
        self.assertEqual(len(preview.image_palette),0)
        volume(preview.parts[0])

    def test_picture_colors_survive_size_change_without_requantization(self):
        opts=PictureSettings(image_data=sample(),resolution=48,color_count=2)
        _quantize.cache_clear()
        plate(content_type="image",picture=opts,width_mm=80,height_mm=32)
        hit=_quantize.cache_info().hits
        plate(content_type="image",picture=opts,width_mm=100,height_mm=35)
        self.assertGreater(_quantize.cache_info().hits,hit)

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

    def test_face_down_image_is_mirrored_in_3mf_but_not_2d_preview(self):
        # Source: blue on the left, red on the right. Since the picture is
        # printed on Z=0 (face-down), the XY geometry must be horizontally
        # mirrored as viewed from the top of the printer. After the user
        # turns the part over about Y, the face must read as the original.
        picture=PictureSettings(image_data=sample(),resolution=24,
                                color_count=2,fit_mode="manual",
                                width_mm=40,x_mm=8,layer_mm=0.4)
        indices, colors, url=optimized_picture(picture)
        self.assertEqual(colors[int(indices[indices.shape[0]//2,0])],"#2244BB")
        self.assertEqual(colors[int(indices[indices.shape[0]//2,-1])],"#EE3322")
        bitmap=Image.open(io.BytesIO(base64.b64decode(url.split(",",1)[1])))
        self.assertEqual(bitmap.getpixel((0,bitmap.height//2))[:3],(34,68,187))
        self.assertEqual(bitmap.getpixel((bitmap.width-1,bitmap.height//2))[:3],(238,51,34))

        model=plate(content_type="image",width_mm=90,height_mm=40,
                    shape="rectangle",picture=picture)
        images={part.color:part for part in model.parts if "Изображение" in part.name}
        self.assertEqual(set(images),{"#2244BB","#EE3322"})
        center=lambda part:(min(v[0] for v in part.vertices)+max(v[0] for v in part.vertices))/2
        self.assertGreater(center(images["#2244BB"]),picture.x_mm)
        self.assertLess(center(images["#EE3322"]),picture.x_mm)
        for part in images.values():
            self.assertAlmostEqual(min(v[2] for v in part.vertices),0,places=5)
            self.assertAlmostEqual(max(v[2] for v in part.vertices),0.4,places=5)
            volume(part)

        # Check actual export, not just the intermediate preview parts.
        with zipfile.ZipFile(io.BytesIO(make_3mf(model))) as archive:
            root=ET.fromstring(archive.read("3D/3dmodel.model"))
        materials=root.findall(f".//{{{CORE}}}basematerials/{{{CORE}}}base")
        exported={}
        for obj in root.findall(f".//{{{CORE}}}object"):
            mesh=obj.find(f"{{{CORE}}}mesh")
            if mesh is None:
                continue
            color=materials[int(obj.attrib["pindex"])].attrib["displaycolor"][:7]
            if color not in images:
                continue
            xs=[float(node.attrib["x"]) for node in mesh.findall(
                f"{{{CORE}}}vertices/{{{CORE}}}vertex")]
            exported[color]=(min(xs)+max(xs))/2
        self.assertGreater(exported["#2244BB"],picture.x_mm)
        self.assertLess(exported["#EE3322"],picture.x_mm)

    def test_diagonal_touching_color_islands_form_closed_shells(self):
        # Disconnected color islands can meet at a vertex. Their walls must
        # remain separate indexed shells, not be merged into a non-manifold
        # edge with four incident faces.
        from shapely.geometry import MultiPolygon, box
        from shapes.geometry import extrude
        color=extrude(MultiPolygon([box(0,0,1,1),box(1,1,2,2)]),
                      0,0.4,"Two diagonal islands","#FFFFFF")
        m=trimesh.Trimesh(vertices=color.vertices,faces=color.faces,process=False)
        self.assertTrue(m.is_watertight)
        self.assertTrue(trimesh.Trimesh(vertices=color.vertices,faces=color.faces,
                                       process=True).is_watertight)
        self.assertAlmostEqual(m.volume,0.8,places=3)

    def test_color_regions_with_kissing_inner_holes_export(self):
        # An image region may contain several holes that share an exact
        # corner. The body remains mathematically valid in 2D but must be
        # separated by a sub-print-resolution slit in the 3D wall mesh.
        from shapely.geometry import box
        from shapely.ops import unary_union
        from shapes.geometry import extrude
        p=box(0,0,10,10).difference(unary_union([
            box(1,1,3,3),box(3,3,5,5),box(5,5,7,7)
        ]))
        self.assertTrue(p.is_valid)
        part=extrude(p,0,0.4,"Background with touching holes","#FFFFFF")
        self.assertGreater(volume(part),0)

    def test_busy_multicolor_logo_with_rounded_base(self):
        # Regression for 422 from screenshot: 100x100 rounded plate with
        # 1 mm corners, top-round 0.3 mm, 160 px raster, 4 colors.
        # Multiple touching holes and disconnected color islands.
        image=Image.new("RGB",(180,120),"white")
        draw=ImageDraw.Draw(image)
        for x in range(0,180,3):
            for y in range(0,120,3):
                if (x+y)%13<=6:
                    draw.rectangle((x,y,x+2,y+2),
                                   fill=(x*3%256,y*3%256,(x+y)%256))
        raw=io.BytesIO()
        image.save(raw,format="PNG")
        url="data:image/png;base64,"+base64.b64encode(raw.getvalue()).decode()
        for rounding in (0,0.3):
            with self.subTest(rounding=rounding):
                opts=PictureSettings(image_data=url,resolution=160,color_count=4)
                result=plate(content_type="image",picture=opts,
                             shape="rounded",corner_radius_mm=1,
                             width_mm=100,height_mm=100,thickness_mm=3,
                             top_round_mm=rounding,base_color="#000000")
                self.assertEqual(len(result.image_palette),4)
                self.assertEqual(len(result.parts),6)
                for part in result.parts:
                    volume(part)
                archive=make_3mf(result)
                self.assertGreater(len(archive),10000)

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
