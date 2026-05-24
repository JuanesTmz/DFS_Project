"""
Endpoints de gestión de DataNodes: registro, heartbeat y listado.
"""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from app.database import get_db
from app.models import DataNodeHeartbeatRequest, DataNodeInfo, DataNodeRegisterRequest

router = APIRouter()


@router.post("/register")
def register_datanode(
    body: DataNodeRegisterRequest,
    db: sqlite3.Connection = Depends(get_db),
):
    # Upsert: registra el nodo o actualiza sus datos si ya existe
    db.execute(
        """INSERT INTO datanodes (datanode_id, host, port, last_heartbeat, is_active)
           VALUES (?, ?, ?, datetime('now'), 1)
           ON CONFLICT(datanode_id) DO UPDATE SET
               host           = excluded.host,
               port           = excluded.port,
               last_heartbeat = datetime('now'),
               is_active      = 1""",
        (body.datanode_id, body.host, body.port),
    )
    db.commit()
    print(f"[NameNode] DataNode registrado: {body.datanode_id} @ {body.host}:{body.port}")
    return {"message": "DataNode registrado"}


@router.post("/heartbeat")
def heartbeat(
    body: DataNodeHeartbeatRequest,
    db: sqlite3.Connection = Depends(get_db),
):
    result = db.execute(
        "UPDATE datanodes SET last_heartbeat = datetime('now'), is_active = 1 WHERE datanode_id = ?",
        (body.datanode_id,),
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="DataNode no registrado")
    db.commit()
    return {"message": "ok"}


@router.get("/list", response_model=list[DataNodeInfo])
def list_datanodes(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute("SELECT * FROM datanodes ORDER BY datanode_id").fetchall()
    return [DataNodeInfo(**dict(row)) for row in rows]
