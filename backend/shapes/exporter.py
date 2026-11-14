"""3MF core + basematerials, with grouped multicolor components; and STL."""
from io import BytesIO
import zipfile
from xml.etree import ElementTree as ET

import numpy as np
import trimesh

from .schemas import Preview

CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
MAT = "http://schemas.microsoft.com/3dmanufacturing/material/2015/02"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
ET.register_namespace("", CORE)
ET.register_namespace("m", MAT)


def make_3mf(model: Preview) -> bytes:
    root = ET.Element(f"{{{CORE}}}model", {"unit": "millimeter", "xml:lang": "en-US"})
    ET.SubElement(root, f"{{{CORE}}}metadata", {"name": "Title"}).text = "ShapeHatch — изделие для печати"
    ET.SubElement(root, f"{{{CORE}}}metadata", {"name": "Application"}).text = "ShapeHatch"
    resources = ET.SubElement(root, f"{{{CORE}}}resources")
    colors = list(dict.fromkeys(part.color for part in model.parts))
    materials = ET.SubElement(resources, f"{{{CORE}}}basematerials", {"id": "1"})
    for i, color in enumerate(colors):
        ET.SubElement(materials, f"{{{CORE}}}base",
                      {"name": f"Filament {i+1} — {color.upper()}", "displaycolor": color.upper() + "FF"})

    for part_id, part in enumerate(model.parts, start=2):
        obj = ET.SubElement(resources, f"{{{CORE}}}object", {
            "id": str(part_id), "type": "model", "pid": "1", "pindex": str(colors.index(part.color)),
            "name": part.name, "partnumber": f"SH-{part_id:03d}"})
        mesh = ET.SubElement(obj, f"{{{CORE}}}mesh")
        vertices = ET.SubElement(mesh, f"{{{CORE}}}vertices")
        for x, y, z in part.vertices:
            ET.SubElement(vertices, f"{{{CORE}}}vertex",
                          {"x": str(x), "y": str(y), "z": str(z)})
        faces = ET.SubElement(mesh, f"{{{CORE}}}triangles")
        for a, b, c in part.faces:
            ET.SubElement(faces, f"{{{CORE}}}triangle",
                          {"v1": str(a), "v2": str(b), "v3": str(c)})

    # One model item containing all color parts, so a slicer keeps their alignment.
    parent_id = len(model.parts) + 2
    assembly = ET.SubElement(resources, f"{{{CORE}}}object",
                             {"id": str(parent_id), "type": "model",
                              "name": "ShapeHatch — изделие (составные части)"})
    components = ET.SubElement(assembly, f"{{{CORE}}}components")
    for part_id in range(2, len(model.parts) + 2):
        ET.SubElement(components, f"{{{CORE}}}component", {"objectid": str(part_id)})
    build = ET.SubElement(root, f"{{{CORE}}}build")
    ET.SubElement(build, f"{{{CORE}}}item", {"objectid": str(parent_id)})

    content_types = ('<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
        '</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>'
        f'<Relationships xmlns="{PKG}">'
        '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
        '</Relationships>')
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("3D/3dmodel.model", ET.tostring(root, encoding="utf-8", xml_declaration=True))
    return buffer.getvalue()


def _stl(part):
    mesh = trimesh.Trimesh(vertices=np.array(part.vertices), faces=np.array(part.faces), process=False)
    return trimesh.exchange.stl.export_stl(mesh)


def make_stl(model: Preview) -> bytes:
    mesh = trimesh.util.concatenate([
        trimesh.Trimesh(vertices=np.array(part.vertices), faces=np.array(part.faces), process=False)
        for part in model.parts
    ])
    return trimesh.exchange.stl.export_stl(mesh)


def make_stl_zip(model: Preview) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for i, part in enumerate(model.parts, 1):
            archive.writestr(f"part_{i}_{part.color.lstrip('#')}.stl", _stl(part))
        archive.writestr("README.txt", "STL parts share the same coordinates (mm). Import them as one multipart object into your slicer.\n")
    return buffer.getvalue()
