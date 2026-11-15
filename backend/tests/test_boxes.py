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

from gallery import GalleryStore, owner_from_key
from shapes.boxes import box_openings, rounded_rectangle
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
            (dict(width_mm=30, depth_mm=30, mode="divided", rows=6, columns=6), "Отделения"),
            (dict(width_mm=40, corner_radius_mm=30), "Скругление"),
        ):
            with self.subTest(params=params):
                with self.assertRaisesRegex(ValueError, pattern):
                    self.build(**params)
        with self.assertRaises(ValueError):
            generate(GenerateRequest(kind="box"))


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