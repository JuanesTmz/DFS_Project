"""
NameNode — servidor central de metadatos del DFS.
Gestiona ubicación de bloques, autenticación y coordinación de DataNodes.
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import get_db_direct, init_db
from app.routes import auth, datanodes, dirs, files


async def heartbeat_monitor():
    """Corre cada 30 s. Marca inactivos los DataNodes sin heartbeat reciente."""
    while True:
        await asyncio.sleep(30)
        db = get_db_direct()
        cursor = db.execute(
            """UPDATE datanodes
               SET is_active = 0
               WHERE is_active = 1
                 AND (julianday('now') - julianday(last_heartbeat)) * 86400 > ?""",
            (settings.heartbeat_timeout,),
        )
        if cursor.rowcount:
            print(f"[NameNode] heartbeat_monitor: {cursor.rowcount} nodo(s) marcado(s) inactivo(s)")
        db.commit()
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    task = asyncio.create_task(heartbeat_monitor())
    yield
    task.cancel()


app = FastAPI(
    title="DFS NameNode",
    description="Servidor central de metadatos del sistema de archivos distribuido",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth.router,      prefix="/auth",      tags=["auth"])
app.include_router(files.router,     prefix="/files",     tags=["files"])
app.include_router(dirs.router,      prefix="/dirs",      tags=["dirs"])
app.include_router(datanodes.router, prefix="/datanode",  tags=["datanodes"])


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "component": "namenode"}
