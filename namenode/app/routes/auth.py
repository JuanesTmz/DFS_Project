"""
Endpoints de autenticación: registro e inicio de sesión.
"""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from app.auth import create_token, hash_password, verify_password
from app.database import get_db
from app.models import LoginRequest, RegisterRequest, TokenResponse

router = APIRouter()


@router.post("/register")
def register(body: RegisterRequest, db: sqlite3.Connection = Depends(get_db)):
    existing = db.execute(
        "SELECT id FROM users WHERE username = ?", (body.username,)
    ).fetchone()
    if existing:
        raise HTTPException(status_code=409, detail="El usuario ya existe")
    db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (body.username, hash_password(body.password)),
    )
    db.commit()
    return {"message": "Usuario registrado correctamente"}


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute(
        "SELECT * FROM users WHERE username = ?", (body.username,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")
    token = create_token({"sub": row["username"], "user_id": row["id"]})
    return TokenResponse(access_token=token)
