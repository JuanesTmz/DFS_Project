"""
Cliente CLI del DFS.
Permite subir, bajar y gestionar archivos en el sistema distribuido.

Uso:
    python dfs_client.py <comando> [opciones]

Comandos:
    register  Registrar nuevo usuario
    login     Iniciar sesión
    logout    Cerrar sesión
    put       Subir archivo al DFS
    get       Descargar archivo del DFS
    ls        Listar archivos y directorios
    mkdir     Crear directorio
    rmdir     Eliminar directorio vacío
    rm        Eliminar archivo
"""
import argparse
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from rich.console import Console

load_dotenv(Path(__file__).parent / ".env")

console = Console()
TOKEN_FILE = Path.home() / ".dfs_token"


# ─── Helpers de configuración y token ────────────────────────────────────────

def get_namenode_url() -> str:
    return os.getenv("NAMENODE_URL", "http://localhost:8000").rstrip("/")


def load_token() -> str | None:
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text().strip()
    return None


def save_token(token: str):
    TOKEN_FILE.write_text(token)


def delete_token():
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()


def require_token() -> str:
    token = load_token()
    if not token:
        console.print("[red]Debes hacer login primero.[/red]")
        sys.exit(1)
    return token


# ─── Cliente HTTP ─────────────────────────────────────────────────────────────

def api_call(
    method: str,
    path: str,
    *,
    token: str = None,
    check_auth: bool = True,
    **kwargs,
) -> httpx.Response:
    """Realiza una llamada HTTP al NameNode con manejo de errores comunes."""
    url = f"{get_namenode_url()}{path}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = httpx.request(method, url, headers=headers, **kwargs)
    except httpx.ConnectError:
        console.print(f"[red]No se puede conectar al NameNode en {get_namenode_url()}[/red]")
        sys.exit(1)

    if check_auth and r.status_code == 401:
        console.print("[red]Sesión expirada. Haz login de nuevo.[/red]")
        sys.exit(1)
    if r.status_code == 503:
        console.print("[red]El DFS no tiene suficientes nodos disponibles.[/red]")
        sys.exit(1)

    return r


# ─── Comandos Paso 13: auth ───────────────────────────────────────────────────

def cmd_register(args):
    r = api_call(
        "POST", "/auth/register",
        json={"username": args.user, "password": args.password},
        check_auth=False,
    )
    if r.status_code == 200:
        console.print(f"[green]Usuario '{args.user}' registrado correctamente.[/green]")
    elif r.status_code == 409:
        console.print(f"[red]El usuario '{args.user}' ya existe.[/red]")
    else:
        console.print(f"[red]Error {r.status_code}: {r.json().get('detail', r.text)}[/red]")


def cmd_login(args):
    r = api_call(
        "POST", "/auth/login",
        json={"username": args.user, "password": args.password},
        check_auth=False,
    )
    if r.status_code == 200:
        save_token(r.json()["access_token"])
        console.print(f"[green]Sesión iniciada como {args.user}[/green]")
    elif r.status_code == 404:
        console.print(f"[red]Usuario '{args.user}' no encontrado.[/red]")
    elif r.status_code == 401:
        console.print("[red]Contraseña incorrecta.[/red]")
    else:
        console.print(f"[red]Error {r.status_code}: {r.json().get('detail', r.text)}[/red]")


def cmd_logout(args):
    delete_token()
    console.print("[green]Sesión cerrada.[/green]")


# ─── Comandos Paso 14: put / get ──────────────────────────────────────────────

def cmd_put(args):
    # Implementado en Paso 14
    raise NotImplementedError


def cmd_get(args):
    # Implementado en Paso 14
    raise NotImplementedError


# ─── Comandos Paso 15: ls / mkdir / rmdir / rm ────────────────────────────────

def cmd_ls(args):
    # Implementado en Paso 15
    raise NotImplementedError


def cmd_mkdir(args):
    # Implementado en Paso 15
    raise NotImplementedError


def cmd_rmdir(args):
    # Implementado en Paso 15
    raise NotImplementedError


def cmd_rm(args):
    # Implementado en Paso 15
    raise NotImplementedError


# ─── Parser ───────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dfs",
        description="Cliente CLI del Sistema de Archivos Distribuido",
    )
    sub = parser.add_subparsers(dest="command", metavar="<comando>")
    sub.required = True

    # register
    p = sub.add_parser("register", help="Registrar nuevo usuario")
    p.add_argument("--user", required=True, help="Nombre de usuario")
    p.add_argument("--pass", dest="password", required=True, help="Contraseña")
    p.set_defaults(func=cmd_register)

    # login
    p = sub.add_parser("login", help="Iniciar sesión")
    p.add_argument("--user", required=True, help="Nombre de usuario")
    p.add_argument("--pass", dest="password", required=True, help="Contraseña")
    p.set_defaults(func=cmd_login)

    # logout
    p = sub.add_parser("logout", help="Cerrar sesión")
    p.set_defaults(func=cmd_logout)

    # put
    p = sub.add_parser("put", help="Subir archivo al DFS")
    p.add_argument("local_path", help="Ruta local del archivo a subir")
    p.add_argument("--dir", default="/", help="Directorio destino en el DFS (default: /)")
    p.set_defaults(func=cmd_put)

    # get
    p = sub.add_parser("get", help="Descargar archivo del DFS")
    p.add_argument("filename", help="Nombre del archivo en el DFS")
    p.add_argument("--dir", default="/", help="Directorio del archivo (default: /)")
    p.set_defaults(func=cmd_get)

    # ls
    p = sub.add_parser("ls", help="Listar archivos y directorios")
    p.add_argument("--dir", default="/", help="Directorio a listar (default: /)")
    p.set_defaults(func=cmd_ls)

    # mkdir
    p = sub.add_parser("mkdir", help="Crear directorio")
    p.add_argument("path", help="Ruta del nuevo directorio")
    p.set_defaults(func=cmd_mkdir)

    # rmdir
    p = sub.add_parser("rmdir", help="Eliminar directorio vacío")
    p.add_argument("path", help="Ruta del directorio a eliminar")
    p.set_defaults(func=cmd_rmdir)

    # rm
    p = sub.add_parser("rm", help="Eliminar archivo del DFS")
    p.add_argument("filename", help="Nombre del archivo a eliminar")
    p.add_argument("--dir", default="/", help="Directorio del archivo (default: /)")
    p.set_defaults(func=cmd_rm)

    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
