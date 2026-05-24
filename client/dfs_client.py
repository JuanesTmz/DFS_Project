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
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn, TimeRemainingColumn
from rich.table import Table

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


# ─── Helpers de transferencia de bloques ─────────────────────────────────────

def _upload_block(block_id: str, data: bytes, datanode: dict):
    url = f"http://{datanode['host']}:{datanode['port']}/blocks/upload/{block_id}"
    try:
        r = httpx.post(
            url,
            files={"file": (f"{block_id}.bin", data, "application/octet-stream")},
            timeout=120,
        )
        if r.status_code != 200:
            console.print(f"[red]Error al subir bloque {block_id} a {datanode['datanode_id']}: {r.text}[/red]")
            sys.exit(1)
    except httpx.ConnectError:
        console.print(
            f"[red]No se puede conectar al DataNode {datanode['datanode_id']} "
            f"({datanode['host']}:{datanode['port']})[/red]"
        )
        sys.exit(1)


def _confirm_block(token: str, block_id: str, datanode_id: str, size_bytes: int, is_primary: bool):
    api_call(
        "POST", "/files/confirm_block",
        token=token,
        json={
            "block_id": block_id,
            "datanode_id": datanode_id,
            "size_bytes": size_bytes,
            "is_primary": is_primary,
        },
    )


# ─── Comandos Paso 14: put / get ──────────────────────────────────────────────

def cmd_put(args):
    token = require_token()
    local_path = Path(args.local_path)

    if not local_path.exists():
        console.print(f"[red]Archivo no encontrado: {local_path}[/red]")
        sys.exit(1)

    file_size = local_path.stat().st_size
    filename = local_path.name

    r = api_call(
        "POST", "/files/put",
        token=token,
        json={"filename": filename, "file_size": file_size, "directory": args.dir},
    )
    if r.status_code != 200:
        console.print(f"[red]Error al registrar archivo: {r.json().get('detail', r.text)}[/red]")
        sys.exit(1)

    put_resp = r.json()
    total_blocks = put_resp["total_blocks"]
    block_size = put_resp["block_size_bytes"]
    assignments = put_resp["assignments"]

    progress_cols = [
        TextColumn("[cyan]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
    ]
    with open(local_path, "rb") as fh:
        with Progress(*progress_cols, console=console) as progress:
            task = progress.add_task(f"Subiendo {filename}", total=total_blocks)

            for assignment in assignments:
                idx = assignment["block_index"]
                block_id = assignment["block_id"]
                primary = assignment["primary_datanode"]
                replica = assignment["replica_datanode"]

                fh.seek(idx * block_size)
                chunk = fh.read(block_size)

                _upload_block(block_id, chunk, primary)
                _confirm_block(token, block_id, primary["datanode_id"], len(chunk), is_primary=True)

                _upload_block(block_id, chunk, replica)
                _confirm_block(token, block_id, replica["datanode_id"], len(chunk), is_primary=False)

                progress.advance(task)

    table = Table(title=f"Bloques de [bold]{filename}[/bold]")
    table.add_column("Bloque", style="cyan", justify="right")
    table.add_column("Primario", style="green")
    table.add_column("Réplica", style="yellow")
    for a in assignments:
        p = a["primary_datanode"]
        rep = a["replica_datanode"]
        table.add_row(
            str(a["block_index"]),
            f"{p['datanode_id']} ({p['host']}:{p['port']})",
            f"{rep['datanode_id']} ({rep['host']}:{rep['port']})",
        )
    console.print(table)
    console.print(f"[green]'{filename}' subido en {total_blocks} bloque(s).[/green]")


def cmd_get(args):
    token = require_token()

    r = api_call(
        "GET", f"/files/get/{args.filename}",
        token=token,
        params={"directory": args.dir},
    )
    if r.status_code == 404:
        console.print(f"[red]Archivo '{args.filename}' no encontrado en el DFS.[/red]")
        sys.exit(1)
    if r.status_code != 200:
        console.print(f"[red]Error {r.status_code}: {r.json().get('detail', r.text)}[/red]")
        sys.exit(1)

    get_resp = r.json()
    blocks = sorted(get_resp["blocks"], key=lambda b: b["block_index"])
    output_path = Path(args.filename)

    progress_cols = [
        TextColumn("[cyan]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
    ]
    with open(output_path, "wb") as fh:
        with Progress(*progress_cols, console=console) as progress:
            task = progress.add_task(f"Descargando {args.filename}", total=len(blocks))

            for block in blocks:
                block_id = block["block_id"]
                data = None

                for dn in block["datanodes"]:
                    try:
                        url = f"http://{dn['host']}:{dn['port']}/blocks/download/{block_id}"
                        resp = httpx.get(url, timeout=120)
                        if resp.status_code == 200:
                            data = resp.content
                            break
                    except httpx.ConnectError:
                        continue

                if data is None:
                    console.print(
                        f"[red]No se pudo recuperar el bloque {block_id} "
                        f"de ningún DataNode.[/red]"
                    )
                    sys.exit(1)

                fh.write(data)
                progress.advance(task)

    console.print(f"[green]'{args.filename}' descargado correctamente → {output_path.resolve()}[/green]")


# ─── Comandos Paso 15: ls / mkdir / rmdir / rm ────────────────────────────────

def _fmt_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def cmd_ls(args):
    token = require_token()
    r = api_call("GET", "/files/ls", token=token, params={"directory": args.dir})
    if r.status_code != 200:
        console.print(f"[red]Error {r.status_code}: {r.json().get('detail', r.text)}[/red]")
        sys.exit(1)

    data = r.json()
    console.print(f"\n[bold]Directorio:[/bold] {data['directory']}\n")

    if data["subdirectories"]:
        for d in data["subdirectories"]:
            console.print(f"  [blue]{d}/[/blue]")
        console.print()

    if not data["files"]:
        console.print("[dim]  (vacío)[/dim]")
        return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Nombre", style="cyan")
    table.add_column("Tamaño", justify="right")
    table.add_column("Bloques", justify="right")
    table.add_column("Creado", style="dim")
    for f in data["files"]:
        table.add_row(
            f["filename"],
            _fmt_size(f["size_bytes"]),
            str(f["total_blocks"]),
            f["created_at"],
        )
    console.print(table)


def cmd_mkdir(args):
    token = require_token()
    r = api_call("POST", "/dirs/mkdir", token=token, json={"path": args.path})
    if r.status_code == 200:
        console.print(f"[green]Directorio '{args.path}' creado.[/green]")
    elif r.status_code == 409:
        console.print(f"[red]El directorio '{args.path}' ya existe.[/red]")
    else:
        console.print(f"[red]Error {r.status_code}: {r.json().get('detail', r.text)}[/red]")


def cmd_rmdir(args):
    token = require_token()
    r = api_call("DELETE", f"/dirs/rmdir/{args.path}", token=token)
    if r.status_code == 200:
        console.print(f"[green]Directorio '{args.path}' eliminado.[/green]")
    elif r.status_code == 404:
        console.print(f"[red]El directorio '{args.path}' no existe.[/red]")
    elif r.status_code == 400:
        console.print(f"[red]{r.json().get('detail', 'El directorio no está vacío.')}[/red]")
    else:
        console.print(f"[red]Error {r.status_code}: {r.json().get('detail', r.text)}[/red]")


def cmd_rm(args):
    token = require_token()
    confirm = input(f"¿Seguro que deseas eliminar '{args.filename}'? [s/N] ").strip().lower()
    if confirm not in ("s", "si", "sí"):
        console.print("[dim]Operación cancelada.[/dim]")
        return

    r = api_call(
        "DELETE", f"/files/rm/{args.filename}",
        token=token,
        params={"directory": args.dir},
    )
    if r.status_code == 200:
        console.print(f"[green]Archivo '{args.filename}' eliminado.[/green]")
    elif r.status_code == 404:
        console.print(f"[red]Archivo '{args.filename}' no encontrado.[/red]")
    else:
        console.print(f"[red]Error {r.status_code}: {r.json().get('detail', r.text)}[/red]")


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
