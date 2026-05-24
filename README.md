# DFS — Sistema de Archivos Distribuidos por Bloques

Proyecto universitario — Arquitecturas de Nube y Sistemas Distribuidos  
Universidad Pontificia Bolivariana · 2026  
Estudiante: Juan Esteban Trillos Monterroza · ID: 000486388

---

## Descripción

DFS minimalista inspirado en HDFS/GFS. Divide archivos en bloques de 64 MB,
los distribuye entre múltiples DataNodes y los replica para garantizar disponibilidad.

```
Cliente (CLI)
    │
    ├─── REST (metadatos) ──► NameNode  (puerto 8000)
    │                              │
    │                              └─── asigna DataNodes
    │
    └─── REST (bloques) ───► DataNode 1 (puerto 8001)
                             DataNode 2 (puerto 8002)
                             DataNode 3 (puerto 8003)
```

## Componentes

| Componente  | Descripción                                              |
|-------------|----------------------------------------------------------|
| `namenode/` | Servidor central de metadatos (FastAPI + SQLite)         |
| `datanode/` | Servidor de almacenamiento de bloques (FastAPI + disco)  |
| `client/`   | CLI para interactuar con el DFS                          |

## Inicio rápido (Docker Compose — desarrollo local)

```bash
# 1. Clonar el repositorio
git clone <repo-url>
cd dfs

# 2. Copiar variables de entorno
cp namenode/.env.example namenode/.env
cp datanode/.env.example datanode/.env
cp client/.env.example client/.env

# 3. Levantar el clúster completo
docker compose up --build

# 4. Usar el cliente
cd client
python dfs_client.py register --user juan --pass 1234
python dfs_client.py login    --user juan --pass 1234
python dfs_client.py put archivo_grande.mp4
python dfs_client.py get archivo_grande.mp4
python dfs_client.py ls
```

## Variables de entorno

### NameNode (`namenode/.env`)
```
BLOCK_SIZE_MB=64
REPLICATION_FACTOR=2
HEARTBEAT_TIMEOUT=90
SECRET_KEY=cambia_esto_en_produccion
```

### DataNode (`datanode/.env`)
```
NAMENODE_URL=http://namenode:8000
DATANODE_ID=datanode-1
DATANODE_PORT=8001
HEARTBEAT_INTERVAL=30
STORAGE_PATH=/data/blocks
```

### Cliente (`client/.env`)
```
NAMENODE_URL=http://localhost:8000
```

## Despliegue en AWS

Ver sección de despliegue en el informe técnico.  
Infraestructura: 4 instancias EC2 (t2.micro) con Ubuntu 24.04 + Docker.

## Comandos CLI disponibles

```
register --user <u> --pass <p>   Registrar nuevo usuario
login    --user <u> --pass <p>   Iniciar sesión
put      <ruta_local>            Subir archivo al DFS
get      <nombre_archivo>        Descargar archivo del DFS
ls       [directorio]            Listar archivos
mkdir    <directorio>            Crear directorio
rmdir    <directorio>            Eliminar directorio
rm       <nombre_archivo>        Eliminar archivo
logout                           Cerrar sesión
```

## Stack tecnológico

- **Python 3.11**
- **FastAPI** + Uvicorn
- **SQLite** (metadatos en NameNode)
- **Docker** + Docker Compose
- **AWS Academy** (EC2, Security Groups)
