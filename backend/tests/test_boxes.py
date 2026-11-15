"""Printable, single-shell box geometry, gallery and export regression tests."""
import io
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4
import zipfile

import numpy as np
from fastapi import HTTPException
import trimesh
from shapely.geometry import Point
from shapely.ops import unary_union

from gallery import GalleryStore, owner_from_key
from shapes.boxes import box_openings, rounded_rectangle, build_box
from shapes.build import generate
from shapes.exporter import make_3mf, make_stl, make_stl_zip
from shapes.schemas import BoxOptions, GenerateRequest


class BoxGeneratorTests(unittest.TestCase):
    def build(self, **params):
        opts = BoxOptions(**params)
        result = generate(GenerateRequest(kind="box", box=opts))
        for part in result.parts:
            mesh = trimesh.Trimesh(vertices=np.array(part.vertices),
                                   faces=np.array(part.faces), process=False)
            self.assertTrue(mesh.is_watertight, part.name)
            self.assertTrue(mesh.is_winding_consistent, part.name)
            self.assertGreater(mesh.volume, 0, part.name)
            # Faces must form one connected piece; avoid an optional trimesh
            # networkx/scipy graph dependency in the minimal API image.
            edge_owner = {}
            neighbours = [set() for _ in part.faces]
            for index, (a, b, c) in enumerate(part.faces):
                for edge in ((a, b), (b, c), (c, a)):
                    key = tuple(sorted(edge))
                    previous = edge_owner.setdefault(key, index)
                    if previous != index:
                        neighbours[index].add(previous)
                        neighbours[previous].add(index)
            visited = {0}
            pending = [0]
            while pending:
                for adjacent in neighbours[pending.pop()]:
                    if adjacent not in visited:
                        visited.add(adjacent)
                        pending.append(adjacent)
            self.assertEqual(len(visited), len(part.faces), part.name)
        return opts, result

    def test_open_box_is_single_watertight_hollow_body(self):
        opts, result = self.build(mode="open")
        self.assertEqual(len(result.parts), 1)
        self.assertEqual(result.size_mm, [100, 75, 45])
        outer = rounded_rectangle(opts.width_mm, opts.depth_mm, opts.corner_radius_mm)
        holes = box_openings(opts, outer)
        volume = outer.area * opts.height_mm - sum(
            region.area for region in holes) * (opts.height_mm - opts.bottom_mm)
        body = result.parts[0]
        mesh = trimesh.Trimesh(vertices=body.vertices, faces=body.faces, process=False)
        self.assertAlmostEqual(mesh.volume, volume, delta=0.5)

    def test_dividers_are_integral_and_reduce_cavity_volume(self):
        open_options, open_box = self.build(mode="open")
        divided_options, result = self.build(mode="divided", columns=3, rows=2,
                                             divider_mm=2.5)
        self.assertEqual(len(result.parts), 1)
        outer = rounded_rectangle(divided_options.width_mm, divided_options.depth_mm,
                                  divided_options.corner_radius_mm)
        self.assertEqual(len(box_openings(divided_options, outer)), 6)
        open_vol = trimesh.Trimesh(vertices=open_box.parts[0].vertices,
                                  faces=open_box.parts[0].faces, process=False).volume
        divider_vol = trimesh.Trimesh(vertices=result.parts[0].vertices,
                                     faces=result.parts[0].faces, process=False).volume
        self.assertGreater(divider_vol, open_vol)

    def test_lid_is_second_closed_part_laid_beside_box(self):
        opts, result = self.build(mode="lid", lid_clearance_mm=0.35)
        self.assertEqual(len(result.parts), 2)
        body, lid = result.parts
        body_xmax = max(v[0] for v in body.vertices)
        lid_xmin = min(v[0] for v in lid.vertices)
        self.assertAlmostEqual(lid_xmin - body_xmax, 12, places=4)
        self.assertEqual(min(v[2] for v in lid.vertices), 0)
        self.assertEqual(max(v[2] for v in lid.vertices),
                         opts.lid_top_mm + opts.lid_skirt_mm)
        expected_width = opts.width_mm + 2*(opts.lid_clearance_mm+opts.lid_wall_mm)
        self.assertAlmostEqual(max(v[0] for v in lid.vertices)-lid_xmin,
                               expected_width, places=4)
        self.assertIn("переверните", " ".join(result.warnings))

    def test_export_stl_3mf_and_multi_part_zip(self):
        _, result = self.build(mode="lid")
        stl = make_stl(result)
        self.assertGreater(len(stl), 1000)
        with zipfile.ZipFile(io.BytesIO(make_stl_zip(result))) as archive:
            self.assertEqual(len([n for n in archive.namelist() if n.endswith(".stl")]), 2)
        with zipfile.ZipFile(io.BytesIO(make_3mf(result))) as archive:
            self.assertIn("3D/3dmodel.model", archive.namelist())
        with zipfile.ZipFile(io.BytesIO(make_3mf(result, "orca"))) as archive:
            self.assertIn("Metadata/model_settings.config", archive.namelist())

    def test_dimension_and_partition_limits(self):
        for params, pattern in (
            (dict(height_mm=12, bottom_mm=10), "дна"),
            (dict(width_mm=30, depth_mm=30, mode="divided", rows=6, columns=6), "отделение"),
            (dict(width_mm=40, corner_radius_mm=30), "Скругление"),
        ):
            with self.subTest(params=params):
                with self.assertRaisesRegex(ValueError, pattern):
                    self.build(**params)
        with self.assertRaises(ValueError):
            generate(GenerateRequest(kind="box"))

    def test_one_large_cell_and_three_small_cells(self):
        options, result = self.build(sections_enabled=True, columns=3, rows=2,
            merged_cells=[dict(row=0, col=0, colspan=3, rowspan=1)])
        outer = rounded_rectangle(options.width_mm, options.depth_mm,
                                  options.corner_radius_mm)
        cavities = box_openings(options, outer)
        self.assertEqual(len(cavities), 4)
        upper = max(cavities, key=lambda p: p.centroid.y)
        self.assertAlmostEqual(upper.bounds[2] - upper.bounds[0],
                               options.width_mm - 2*options.wall_mm, delta=0.05)
        self.assertEqual(len(result.parts), 1)

    def test_nonuniform_sections_and_long_vertical_merge(self):
        options, _ = self.build(sections_enabled=True, columns=2, rows=3,
            column_weights=[3, 1], row_weights=[1, 1, 1],
            merged_cells=[dict(row=0, col=0, colspan=1, rowspan=3)])
        cavities = box_openings(options, rounded_rectangle(options.width_mm,
            options.depth_mm, options.corner_radius_mm))
        self.assertEqual(len(cavities), 4)
        widest = max(cavities, key=lambda shape: shape.area)
        self.assertGreater(widest.area, 2 * min(x.area for x in cavities))

    def test_lid_and_compartments_are_independent(self):
        for kind in ('over', 'inset'):
            with self.subTest(kind=kind):
                _, result = self.build(sections_enabled=True, columns=3, rows=2,
                    lid_type=kind, merged_cells=[dict(row=0, col=0, colspan=3, rowspan=1)])
                self.assertEqual(len(result.parts), 2)
                body, cover = result.parts
                self.assertAlmostEqual(min(x[2] for x in cover.vertices), 0)
                self.assertIn('крышка', cover.name.lower())

    def test_inset_lid_depth_is_real_geometry(self):
        small_opts, small = self.build(lid_type='inset', lid_skirt_mm=5)
        large_opts, large = self.build(lid_type='inset', lid_skirt_mm=13)
        def cover_volume(model):
            part = model.parts[1]
            return trimesh.Trimesh(vertices=part.vertices,faces=part.faces,
                                   process=False).volume
        self.assertAlmostEqual(max(x[2] for x in small.parts[1].vertices),
                               small_opts.lid_top_mm + 5,places=5)
        self.assertAlmostEqual(max(x[2] for x in large.parts[1].vertices),
                               large_opts.lid_top_mm + 13,places=5)
        self.assertGreater(cover_volume(large),cover_volume(small))

    def test_inset_lip_has_clearance_from_full_height_partitions(self):
        opts, model = self.build(lid_type="inset", sections_enabled=True,
            columns=3, rows=2, merged_cells=[dict(row=0, col=0,
                                                  colspan=3, rowspan=1)])
        outer = rounded_rectangle(opts.width_mm, opts.depth_mm,
                                  opts.corner_radius_mm)
        inner = outer.buffer(-opts.wall_mm, quad_segs=8)
        partitions = inner.difference(unary_union(box_openings(opts, outer)))
        self.assertGreater(partitions.area, 0)
        # The lid lives beside the body in print coordinates; remove X offset.
        lid = model.parts[1]
        offset = opts.width_mm + 12
        lip_tip_z = opts.lid_top_mm + opts.lid_skirt_mm
        tip_points = [(x - offset, y) for x, y, z in lid.vertices
                      if abs(z - lip_tip_z) < 1e-5]
        self.assertGreater(len(tip_points), 20)
        self.assertTrue(all(partitions.distance(Point(x, y)) > opts.lid_clearance_mm
                            for x, y in tip_points))
        self.assertTrue(any("перегородок" in warning for warning in model.warnings))

    def test_legacy_050_projects_preserve_lid_and_dividers(self):
        for old, expected in (('open',1),('lid',2),('divided',1)):
            with self.subTest(mode=old):
                opts = BoxOptions.model_validate({'mode':old,'columns':3,'rows':2})
                self.assertEqual(len(build_box(opts).parts),expected)
                if old == 'divided':
                    self.assertEqual(len(box_openings(opts,rounded_rectangle(
                        opts.width_mm,opts.depth_mm,opts.corner_radius_mm))),6)
        # New explicit fields override any legacy mode, even when both are set.
        _, mixed = self.build(mode='divided',sections_enabled=False,lid_type='inset')
        self.assertEqual(len(mixed.parts),2)

    def test_invalid_merged_layout_and_sizes_rejected(self):
        wrong=[
            dict(sections_enabled=True, columns=2, rows=2,
                 merged_cells=[dict(col=1,row=0,colspan=2,rowspan=1)]),
            dict(sections_enabled=True, columns=3, rows=2,
                 merged_cells=[dict(col=0,row=0,colspan=2,rowspan=2),
                               dict(col=1,row=0,colspan=2,rowspan=1)]),
            dict(sections_enabled=True, columns=3, rows=2,
                 column_weights=[1,2]),
            dict(sections_enabled=True, columns=3, rows=2,
                 column_weights=[100,1,1]),
            dict(lid_type='inset',width_mm=30,depth_mm=30,wall_mm=8,
                 lid_wall_mm=8),
        ]
        for kwargs in wrong:
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                self.build(**kwargs)



class BoxGalleryTests(unittest.TestCase):
    def test_box_round_trip_and_access_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GalleryStore(Path(directory)/"gallery.sqlite3")
            owner = owner_from_key("1"*64)
            stranger = owner_from_key("2"*64)
            pid = str(uuid4())
            entry = dict(id=pid, kind="box", name="Коробка под гайки",
                         updatedAt="old", box=BoxOptions(
                            mode="divided", rows=2, columns=3).model_dump())
            store.put(owner, pid, entry)
            self.assertEqual(store.list(owner)[0]["kind"], "box")
            self.assertEqual(store.get(owner, pid)["box"]["columns"], 3)
            self.assertEqual(store.list(stranger), [])
            with self.assertRaises(HTTPException) as error:
                store.get(stranger, pid)
            self.assertEqual(error.exception.status_code, 404)
            entry["box"]["columns"] = 4
            store.put(owner, pid, entry)
            self.assertEqual(store.get(owner, pid)["box"]["columns"], 4)

    def test_invalid_box_cannot_be_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GalleryStore(Path(directory)/"gallery.sqlite3")
            pid = str(uuid4())
            entry = dict(id=pid, kind="box", name="Недопустимая коробка",
                         box={"width_mm": -1})
            with self.assertRaises(HTTPException) as error:
                store.put(owner_from_key("1"*64), pid, entry)
            self.assertEqual(error.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()