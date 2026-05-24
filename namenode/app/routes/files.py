"""
Endpoints de gestión de archivos: subida, descarga y eliminación.
"""
import math
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import (
    BlockAssignment,
    BlockConfirmRequest,
    BlockLocation,
    DataNodeInfo,
    FileInfo,
    GetResponse,
    LsResponse,
    PutRequest,
    PutResponse,
)

router = APIRouter()

BLOCK_SIZE = settings.block_size_mb * 1024 * 1024  # bytes


def _get_active_datanodes(db: sqlite3.Connection) -> list[DataNodeInfo]:
    rows = db.execute("SELECT * FROM datanodes WHERE is_active = 1").fetchall()
    return [DataNodeInfo(**dict(row)) for row in rows]


# ── PUT ───────────────────────────────────────────────────────────────────────

@router.post("/put", response_model=PutResponse)
def put_file(
    body: PutRequest,
    current_user=Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    user_id = current_user["id"]

    # 1. El archivo no debe existir ya
    if db.execute(
        "SELECT id FROM files WHERE user_id = ? AND directory = ? AND filename = ?",
        (user_id, body.directory, body.filename),
    ).fetchone():
        raise HTTPException(status_code=409, detail="El archivo ya existe")

    # 2. El directorio debe existir (la raíz "/" siempre es válida)
    if body.directory != "/" and not db.execute(
        "SELECT id FROM directories WHERE user_id = ? AND path = ?",
        (user_id, body.directory),
    ).fetchone():
        raise HTTPException(status_code=400, detail="El directorio no existe")

    # 3. Necesitamos al menos 2 DataNodes activos para replicar
    active_nodes = _get_active_datanodes(db)
    if len(active_nodes) < 2:
        raise HTTPException(
            status_code=503, detail="No hay suficientes DataNodes disponibles"
        )

    # 4. Calcular número de bloques
    total_blocks = math.ceil(body.file_size / BLOCK_SIZE) if body.file_size > 0 else 1

    # 5. Asignar DataNodes por bloque en Round-Robin
    assignments: list[BlockAssignment] = []
    n = len(active_nodes)
    for i in range(total_blocks):
        primary = active_nodes[i % n]
        replica = active_nodes[(i + 1) % n]
        assignments.append(
            BlockAssignment(
                block_index=i,
                block_id=f"{body.filename}_{user_id}_{i}",
                primary_datanode=primary,
                replica_datanode=replica,
            )
        )

    # 6. Registrar el archivo en la BD
    file_id = db.execute(
        "INSERT INTO files (user_id, filename, directory, size_bytes, total_blocks) VALUES (?, ?, ?, ?, ?)",
        (user_id, body.filename, body.directory, body.file_size, total_blocks),
    ).lastrowid

    # 7. Registrar cada bloque (size_bytes se actualiza al confirmar)
    for a in assignments:
        db.execute(
            "INSERT INTO blocks (file_id, block_index, block_id, size_bytes) VALUES (?, ?, ?, 0)",
            (file_id, a.block_index, a.block_id),
        )

    db.commit()
    print(f"[NameNode] put: {body.filename} ({total_blocks} bloques) — usuario {user_id}")

    return PutResponse(
        filename=body.filename,
        total_blocks=total_blocks,
        block_size_bytes=BLOCK_SIZE,
        assignments=assignments,
    )


# ── CONFIRM BLOCK ─────────────────────────────────────────────────────────────

@router.post("/confirm_block")
def confirm_block(
    body: BlockConfirmRequest,
    current_user=Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    if not db.execute(
        "SELECT id FROM blocks WHERE block_id = ?", (body.block_id,)
    ).fetchone():
        raise HTTPException(status_code=404, detail="Bloque no encontrado")

    db.execute(
        "INSERT INTO block_locations (block_id, datanode_id, is_primary) VALUES (?, ?, ?)",
        (body.block_id, body.datanode_id, 1 if body.is_primary else 0),
    )
    db.execute(
        "UPDATE blocks SET size_bytes = ? WHERE block_id = ?",
        (body.size_bytes, body.block_id),
    )
    db.commit()
    print(f"[NameNode] confirm_block: {body.block_id} → {body.datanode_id} (primario={body.is_primary})")
    return {"message": "ok"}


# ── GET ───────────────────────────────────────────────────────────────────────

@router.get("/get/{filename}", response_model=GetResponse)
def get_file(
    filename: str,
    directory: str = "/",
    current_user=Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    user_id = current_user["id"]

    file_row = db.execute(
        "SELECT * FROM files WHERE user_id = ? AND directory = ? AND filename = ?",
        (user_id, directory, filename),
    ).fetchone()
    if not file_row:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    block_rows = db.execute(
        "SELECT * FROM blocks WHERE file_id = ? ORDER BY block_index",
        (file_row["id"],),
    ).fetchall()

    blocks: list[BlockLocation] = []
    for block in block_rows:
        location_rows = db.execute(
            """SELECT d.datanode_id, d.host, d.port, d.is_active, d.last_heartbeat,
                      bl.is_primary
               FROM block_locations bl
               JOIN datanodes d ON d.datanode_id = bl.datanode_id
               WHERE bl.block_id = ?
               ORDER BY bl.is_primary DESC""",
            (block["block_id"],),
        ).fetchall()

        active_nodes = [
            DataNodeInfo(**dict(row)) for row in location_rows if row["is_active"]
        ]
        if not active_nodes:
            raise HTTPException(
                status_code=503,
                detail=f"Bloque {block['block_id']} no disponible en ningún DataNode activo",
            )

        blocks.append(
            BlockLocation(
                block_index=block["block_index"],
                block_id=block["block_id"],
                size_bytes=block["size_bytes"],
                datanodes=active_nodes,
            )
        )

    return GetResponse(
        filename=filename,
        total_blocks=file_row["total_blocks"],
        blocks=blocks,
    )


# ── LS ───────────────────────────────────────────────────────────────────────

@router.get("/ls", response_model=LsResponse)
def ls(
    directory: str = "/",
    current_user=Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    user_id = current_user["id"]

    file_rows = db.execute(
        "SELECT * FROM files WHERE user_id = ? AND directory = ? ORDER BY filename",
        (user_id, directory),
    ).fetchall()
    files = [FileInfo(**dict(row)) for row in file_rows]

    # Subdirectorios directos: hijos inmediatos del directorio actual
    prefix = directory.rstrip("/") + "/"
    dir_rows = db.execute(
        "SELECT path FROM directories WHERE user_id = ? AND path LIKE ? ORDER BY path",
        (user_id, prefix + "%"),
    ).fetchall()
    subdirectories = [
        row["path"]
        for row in dir_rows
        if "/" not in row["path"][len(prefix):]  # solo hijos directos
    ]

    return LsResponse(directory=directory, files=files, subdirectories=subdirectories)


# ── DELETE ────────────────────────────────────────────────────────────────────

@router.delete("/rm/{filename}")
def rm_file(
    filename: str,
    directory: str = "/",
    current_user=Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    import httpx

    user_id = current_user["id"]

    file_row = db.execute(
        "SELECT * FROM files WHERE user_id = ? AND directory = ? AND filename = ?",
        (user_id, directory, filename),
    ).fetchone()
    if not file_row:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    # Obtener todos los bloques y sus DataNodes para borrar los datos físicos
    block_rows = db.execute(
        "SELECT block_id FROM blocks WHERE file_id = ?", (file_row["id"],)
    ).fetchall()

    for block in block_rows:
        location_rows = db.execute(
            """SELECT d.host, d.port FROM block_locations bl
               JOIN datanodes d ON d.datanode_id = bl.datanode_id
               WHERE bl.block_id = ?""",
            (block["block_id"],),
        ).fetchall()
        for loc in location_rows:
            url = f"http://{loc['host']}:{loc['port']}/blocks/delete/{block['block_id']}"
            try:
                httpx.delete(url, timeout=5)
            except Exception as e:
                print(f"[NameNode] warning: no se pudo borrar bloque {block['block_id']} en {url}: {e}")

    db.execute("DELETE FROM files WHERE id = ?", (file_row["id"],))
    db.commit()
    print(f"[NameNode] rm: {filename} eliminado — usuario {user_id}")
    return {"message": "Archivo eliminado"}
