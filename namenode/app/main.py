"""
NameNode — servidor central de metadatos del DFS.
Gestiona ubicación de bloques, autenticación y coordinación de DataNodes.
"""
from fastapi import FastAPI

app = FastAPI(
    title="DFS NameNode",
    description="Servidor central de metadatos del sistema de archivos distribuido",
    version="1.0.0",
)


@app.get("/health")
def health():
    return {"status": "ok", "component": "namenode"}
