"""
DataNode — endpoints de almacenamiento de bloques.
"""
import os
from pathlib import Path

import aiofiles
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.config import settings

router = APIRouter()


@router.post("/blocks/upload/{block_id}")
async def upload_block(block_id: str, file: UploadFile = File(...)):
    os.makedirs(settings.storage_path, exist_ok=True)
    path = Path(settings.storage_path) / f"{block_id}.bin"

    contents = await file.read()
    async with aiofiles.open(path, "wb") as f:
        await f.write(contents)

    return {"block_id": block_id, "size_bytes": len(contents), "status": "stored"}


@router.get("/blocks/download/{block_id}")
async def download_block(block_id: str):
    path = Path(settings.storage_path) / f"{block_id}.bin"

    if not path.exists():
        raise HTTPException(status_code=404, detail="Bloque no encontrado")

    async def iterfile():
        async with aiofiles.open(path, "rb") as f:
            while chunk := await f.read(65536):
                yield chunk

    return StreamingResponse(iterfile(), media_type="application/octet-stream")


@router.delete("/blocks/delete/{block_id}")
async def delete_block(block_id: str):
    path = Path(settings.storage_path) / f"{block_id}.bin"
    if path.exists():
        path.unlink()
    return {"status": "deleted"}


@router.get("/health")
def health():
    return {
        "status": "ok",
        "datanode_id": settings.datanode_id,
        "storage_path": settings.storage_path,
    }
