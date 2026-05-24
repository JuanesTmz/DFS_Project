"""
Conexión SQLite y creación de tablas del NameNode.
Usa sqlite3 de la stdlib — sin SQLAlchemy.
"""
import os
import sqlite3
from app.config import settings

# Extraer ruta del archivo desde "sqlite:///./data/namenode.db"
DB_PATH = settings.database_url.replace("sqlite:///", "")

DDL = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS directories (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    path       TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, path)
);

CREATE TABLE IF NOT EXISTS files (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    filename     TEXT NOT NULL,
    directory    TEXT NOT NULL DEFAULT '/',
    size_bytes   INTEGER NOT NULL DEFAULT 0,
    total_blocks INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, directory, filename)
);

CREATE TABLE IF NOT EXISTS blocks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id     INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    block_index INTEGER NOT NULL,
    block_id    TEXT UNIQUE NOT NULL,
    size_bytes  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS block_locations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    block_id    TEXT NOT NULL REFERENCES blocks(block_id) ON DELETE CASCADE,
    datanode_id TEXT NOT NULL,
    is_primary  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS datanodes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    datanode_id    TEXT UNIQUE NOT NULL,
    host           TEXT NOT NULL,
    port           INTEGER NOT NULL,
    last_heartbeat TEXT DEFAULT (datetime('now')),
    is_active      INTEGER NOT NULL DEFAULT 1
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Crea el directorio y todas las tablas si no existen."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = _connect()
    conn.executescript(DDL)
    conn.commit()
    conn.close()
    print("[NameNode] Base de datos inicializada")


def get_db():
    """Dependency de FastAPI — yield de conexión, cierra al terminar el request."""
    conn = _connect()
    try:
        yield conn
    finally:
        conn.close()


def get_db_direct() -> sqlite3.Connection:
    """Conexión directa para uso fuera de FastAPI (ej: heartbeat monitor)."""
    return _connect()
