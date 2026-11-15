import io
import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
import zipfile
from xml.etree import ElementTree as ET

from fastapi import HTTPException

from gallery import GalleryStore, owner_from_key
from shapes.build import generate
from shapes.exporter import make_3mf
from shapes.schemas import GenerateRequest, PlateOptions


class GalleryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = GalleryStore(Path(self.temp.name) / "gallery.sqlite3")
        self.owner = owner_from_key("a" * 64)
        self.other = owner_from_key("b" * 64)
        self.id = str(uuid4())
        self.project = dict(id=self.id, name="Тестовая табличка", kind="plate",
                            updatedAt="old", plate=PlateOptions(text="ПРОВЕРКА").model_dump())

    def tearDown(self):
        self.temp.cleanup()

    def test_save_load_update_and_delete(self):
        result = self.store.put(self.owner, self.id, self.project)
        self.assertNotEqual(result["updatedAt"], "old")
        self.assertEqual(self.store.list(self.owner)[0]["name"], "Тестовая табличка")
        self.assertEqual(self.store.get(self.owner, self.id)["plate"]["text"], "ПРОВЕРКА")
        self.project["plate"]["text"] = "ИЗМЕНЕНО"
        self.store.put(self.owner, self.id, self.project)
        self.assertEqual(len(self.store.list(self.owner)), 1)
        self.assertEqual(self.store.get(self.owner, self.id)["plate"]["text"], "ИЗМЕНЕНО")
        self.store.delete(self.owner, self.id)
        self.assertEqual(self.store.list(self.owner), [])

    def test_galleries_are_isolated(self):
        self.store.put(self.owner, self.id, self.project)
        self.assertEqual(self.store.list(self.other), [])
        with self.assertRaises(HTTPException) as raised:
            self.store.get(self.other, self.id)
        self.assertEqual(raised.exception.status_code, 404)
        with self.assertRaises(HTTPException):
            self.store.delete(self.other, self.id)
        self.assertEqual(len(self.store.list(self.owner)), 1)

    def test_invalid_access_and_project_rejected(self):
        with self.assertRaises(HTTPException):
            owner_from_key("short")
        self.project["id"] = str(uuid4())
        with self.assertRaises(HTTPException) as raised:
            self.store.put(self.owner, self.id, self.project)
        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(self.store.list(self.owner), [])


class Orca3mfTests(unittest.TestCase):
    def test_orca_adds_part_extruders_and_palette_without_affecting_core(self):
        model = generate(GenerateRequest(kind="plate", plate=PlateOptions(text="КОЗА")))
        colors = list(dict.fromkeys(part.color for part in model.parts))
        with zipfile.ZipFile(io.BytesIO(make_3mf(model))) as ordinary:
            self.assertNotIn("Metadata/model_settings.config", ordinary.namelist())
        with zipfile.ZipFile(io.BytesIO(make_3mf(model, "orca"))) as archive:
            self.assertIn("Metadata/model_settings.config", archive.namelist())
            palette = json.loads(archive.read("Metadata/project_settings.config"))
            self.assertEqual(palette["filament_colour"], colors)
            config = ET.fromstring(archive.read("Metadata/model_settings.config"))
            parts = config.findall(".//part")
            self.assertEqual(len(parts), len(model.parts))
            for i, part in enumerate(parts):
                self.assertEqual(int(part.attrib["id"]), i + 2)
                metadata = {m.attrib["key"]: m.attrib["value"] for m in part.findall("metadata")}
                self.assertEqual(int(metadata["extruder"]), colors.index(model.parts[i].color) + 1)
                self.assertIn(model.parts[i].name, metadata["name"])


if __name__ == "__main__":
    unittest.main()