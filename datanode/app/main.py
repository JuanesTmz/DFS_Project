"""
DataNode — servidor de almacenamiento de bloques del DFS.
Recibe, almacena, sirve y replica bloques de datos.
"""
import asyncio
import os
import socket
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.config import settings
from app.routes import blocks


def get_my_host() -> str:
    """Obtener la IP del contenedor para registrarla en el NameNode."""
    return socket.gethostbyname(socket.gethostname())


async def register_with_namenode():
    """Intentar registro con reintentos hasta que el NameNode responda."""
    url = f"{settings.namenode_url}/datanode/register"
    payload = {
        "datanode_id": settings.datanode_id,
        "host": get_my_host(),
        "port": settings.datanode_port,
    }
    async with httpx.AsyncClient() as client:
        for attempt in range(10):
            try:
                r = await client.post(url, json=payload, timeout=5)
                if r.status_code == 200:
                    print(f"[DataNode] Registrado en NameNode como {settings.datanode_id}")
                    return
            except Exception as e:
                print(f"[DataNode] Intento {attempt + 1}/10 de registro fallido: {e}")
            await asyncio.sleep(3)
    print("[DataNode] ERROR: No se pudo registrar en el NameNode")


async def heartbeat_loop():
    """Enviar heartbeat al NameNode cada HEARTBEAT_INTERVAL segundos."""
    url = f"{settings.namenode_url}/datanode/heartbeat"
    payload = {"datanode_id": settings.datanode_id}
    async with httpx.AsyncClient() as client:
        while True:
            await asyncio.sleep(settings.heartbeat_interval)
            try:
                await client.post(url, json=payload, timeout=5)
            except Exception as e:
                print(f"[DataNode] Heartbeat fallido: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.storage_path, exist_ok=True)
    await register_with_namenode()
    task = asyncio.create_task(heartbeat_loop())
    yield
    task.cancel()


app = FastAPI(
    title="DFS DataNode",
    description="Servidor de almacenamiento de bloques del sistema de archivos distribuido",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(blocks.router, tags=["blocks"])
