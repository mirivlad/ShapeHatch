"""Passwordless private project galleries, keyed by a 256-bit client recovery key.

The key is a bearer capability: the server persists only its SHA-256 digest.
A site visitor never receives another visitor's project list. The browser must
keep or back up its recovery key. Public writes have global/per-gallery quotas.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from uuid import UUID

from fastapi import HTTPException

from shapes.schemas import GenerateRequest

KEY = re.compile(r"^[a-fA-F0-9]{64}$")
PER_PROJECT_BYTES = 9_000_000
MAX_PROJECTS_PER_GALLERY = 100
MAX_GALLERY_BYTES = 80_000_000
MAX_TOTAL_BYTES = 500_000_000


def owner_from_key(key: str | None) -> str:
    if not key or not KEY.fullmatch(key):
        raise HTTPException(status_code=401, detail="Необходим ключ доступа к галерее.")
    return hashlib.sha256(bytes.fromhex(key)).hexdigest()


def validate_project(data: object, project_id: str) -> tuple[str, str, str, str]:
    try:
        UUID(project_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Неверный идентификатор проекта.")
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="Ожидался объект проекта.")
    if data.get("id") != project_id:
        raise HTTPException(status_code=422, detail="Идентификатор проекта не совпадает.")
    name = data.get("name")
    if not isinstance(name, str) or not (1 <= len(name.strip()) <= 120):
        raise HTTPException(status_code=422, detail="Название должно содержать 1–120 символов.")
    kind = data.get("kind")
    if kind not in ("plate", "silhouette"):
        raise HTTPException(status_code=422, detail="Неизвестный генератор.")
    if kind == "plate" and not isinstance(data.get("plate"), dict):
        raise HTTPException(status_code=422, detail="Нет параметров таблички.")
    if kind == "silhouette" and not isinstance(data.get("silhouette"), dict):
        raise HTTPException(status_code=422, detail="Нет параметров силуэта.")
    # Validate all settings and imported content before writing to the database.
    try:
        GenerateRequest.model_validate({"kind": kind, kind: data[kind]})
    except Exception as error:
        raise HTTPException(status_code=422, detail="Невозможно сохранить некорректные параметры модели.") from error
    content_type = data["plate"].get("content_type", "text") if kind == "plate" else ""
    timestamp = datetime.now(timezone.utc).isoformat()
    data = dict(data, name=name.strip(), updatedAt=timestamp)
    serialized = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    if len(serialized.encode("utf-8")) > PER_PROJECT_BYTES:
        raise HTTPException(status_code=413, detail="Проект слишком большой для галереи (максимум 9 МБ).")
    return name.strip(), kind, content_type, serialized


class GalleryStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=20000")
        db.execute("""CREATE TABLE IF NOT EXISTS projects (
            owner TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL,
            kind TEXT NOT NULL, content_type TEXT NOT NULL, data TEXT NOT NULL,
            size INTEGER NOT NULL, updated_at TEXT NOT NULL,
            PRIMARY KEY (owner, id)
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_projects_owner ON projects(owner, updated_at DESC)")
        return db

    @contextmanager
    def session(self):
        db = self.connect()
        try:
            with db:
                yield db
        finally:
            db.close()

    def list(self, owner: str):
        with self.session() as db:
            rows = db.execute(
                "SELECT id, name, kind, content_type, updated_at FROM projects "
                "WHERE owner=? ORDER BY updated_at DESC", (owner,)
            ).fetchall()
        return [dict(id=r["id"], name=r["name"], kind=r["kind"],
                     contentType=r["content_type"], updatedAt=r["updated_at"]) for r in rows]

    def get(self, owner: str, project_id: str):
        with self.session() as db:
            row = db.execute("SELECT data FROM projects WHERE owner=? AND id=?",
                             (owner, project_id)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Проект не найден.")
        return json.loads(row["data"])

    def put(self, owner: str, project_id: str, project: object):
        name, kind, content_type, serialized = validate_project(project, project_id)
        size = len(serialized.encode("utf-8"))
        now = json.loads(serialized)["updatedAt"]
        with self.session() as db:
            db.execute("BEGIN IMMEDIATE")
            counts = db.execute(
                "SELECT COUNT(*), COALESCE(SUM(size),0) FROM projects WHERE owner=?", (owner,)
            ).fetchone()
            previous = db.execute(
                "SELECT size FROM projects WHERE owner=? AND id=?", (owner, project_id)
            ).fetchone()
            old_size = previous["size"] if previous else 0
            if counts[0] >= MAX_PROJECTS_PER_GALLERY and not previous:
                raise HTTPException(status_code=409, detail="Лимит 100 проектов на галерею.")
            if counts[1] - old_size + size > MAX_GALLERY_BYTES:
                raise HTTPException(status_code=413, detail="Галерея заполнена (80 МБ).")
            total = db.execute("SELECT COALESCE(SUM(size),0) FROM projects").fetchone()[0]
            if total - old_size + size > MAX_TOTAL_BYTES:
                raise HTTPException(status_code=507, detail="Общее хранилище сервера заполнено.")
            db.execute(
                "INSERT INTO projects (owner,id,name,kind,content_type,data,size,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(owner,id) DO UPDATE SET "
                "name=excluded.name,kind=excluded.kind,content_type=excluded.content_type,"
                "data=excluded.data,size=excluded.size,updated_at=excluded.updated_at",
                (owner, project_id, name, kind, content_type, serialized, size, now)
            )
        return dict(id=project_id, updatedAt=now)

    def delete(self, owner: str, project_id: str):
        with self.session() as db:
            cursor = db.execute("DELETE FROM projects WHERE owner=? AND id=?", (owner, project_id))
            if not cursor.rowcount:
                raise HTTPException(status_code=404, detail="Проект не найден.")


def get_store() -> GalleryStore:
    return GalleryStore(os.environ.get("SHAPEHATCH_GALLERY_DB", "/tmp/shapehatch-gallery.sqlite3"))