"""
Schemas Pydantic para request/response de la API del NameNode.
"""
from pydantic import BaseModel


# ── Auth ──────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── DataNodes ─────────────────────────────────────────────────────────────────

class DataNodeRegisterRequest(BaseModel):
    datanode_id: str
    host: str
    port: int


class DataNodeHeartbeatRequest(BaseModel):
    datanode_id: str


class DataNodeInfo(BaseModel):
    datanode_id: str
    host: str
    port: int
    is_active: bool
    last_heartbeat: str


# ── Archivos ──────────────────────────────────────────────────────────────────

class PutRequest(BaseModel):
    filename: str
    file_size: int
    directory: str = "/"


class BlockAssignment(BaseModel):
    block_index: int
    block_id: str
    primary_datanode: DataNodeInfo
    replica_datanode: DataNodeInfo


class PutResponse(BaseModel):
    filename: str
    total_blocks: int
    block_size_bytes: int
    assignments: list[BlockAssignment]


class BlockLocation(BaseModel):
    block_index: int
    block_id: str
    size_bytes: int
    datanodes: list[DataNodeInfo]


class GetResponse(BaseModel):
    filename: str
    total_blocks: int
    blocks: list[BlockLocation]


class FileInfo(BaseModel):
    filename: str
    directory: str
    size_bytes: int
    total_blocks: int
    created_at: str


class LsResponse(BaseModel):
    directory: str
    files: list[FileInfo]
    subdirectories: list[str]


class BlockConfirmRequest(BaseModel):
    block_id: str
    datanode_id: str
    size_bytes: int
    is_primary: bool
