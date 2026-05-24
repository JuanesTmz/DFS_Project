"""
DataNode — servidor de almacenamiento de bloques del DFS.
Recibe, almacena, sirve y replica bloques de datos.
"""
from fastapi import FastAPI

app = FastAPI(
    title="DFS DataNode",
    description="Servidor de almacenamiento de bloques del sistema de archivos distribuido",
    version="1.0.0",
)


@app.get("/health")
def health():
    return {"status": "ok", "component": "datanode"}
