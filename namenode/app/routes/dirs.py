"""
Endpoints de gestión de directorios: crear y eliminar.
"""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import get_current_user
from app.database import get_db

router = APIRouter()


class MkdirRequest(BaseModel):
    path: str


# ── MKDIR ─────────────────────────────────────────────────────────────────────

@router.post("/mkdir")
def mkdir(
    body: MkdirRequest,
    current_user=Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    user_id = current_user["id"]

    if db.execute(
        "SELECT id FROM directories WHERE user_id = ? AND path = ?",
        (user_id, body.path),
    ).fetchone():
        raise HTTPException(status_code=409, detail="El directorio ya existe")

    db.execute(
        "INSERT INTO directories (user_id, path) VALUES (?, ?)",
        (user_id, body.path),
    )
    db.commit()
    print(f"[NameNode] mkdir: {body.path} — usuario {user_id}")
    return {"message": "Directorio creado"}


# ── RMDIR ─────────────────────────────────────────────────────────────────────

@router.delete("/rmdir/{path:path}")
def rmdir(
    path: str,
    current_user=Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    user_id = current_user["id"]

    if not db.execute(
        "SELECT id FROM directories WHERE user_id = ? AND path = ?",
        (user_id, path),
    ).fetchone():
        raise HTTPException(status_code=404, detail="El directorio no existe")

    # No se puede eliminar si tiene archivos
    if db.execute(
        "SELECT id FROM files WHERE user_id = ? AND directory = ?",
        (user_id, path),
    ).fetchone():
        raise HTTPException(status_code=400, detail="El directorio no está vacío (contiene archivos)")

    # No se puede eliminar si tiene subdirectorios
    prefix = path.rstrip("/") + "/"
    if db.execute(
        "SELECT id FROM directories WHERE user_id = ? AND path LIKE ?",
        (user_id, prefix + "%"),
    ).fetchone():
        raise HTTPException(status_code=400, detail="El directorio no está vacío (contiene subdirectorios)")

    db.execute(
        "DELETE FROM directories WHERE user_id = ? AND path = ?",
        (user_id, path),
    )
    db.commit()
    print(f"[NameNode] rmdir: {path} — usuario {user_id}")
    return {"message": "Directorio eliminado"}
