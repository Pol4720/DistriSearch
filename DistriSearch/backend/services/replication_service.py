"""Replication manager.

Objetivo inicial: cuando un nodo cae (OFFLINE), intentar replicar sus archivos a un repositorio central
para mejorar disponibilidad. Estrategia simple:

- Consideramos 'central' como destino (carpeta CENTRAL_SHARED_FOLDER).
- Para cada file_id cuyo node_id es OFFLINE, intentamos descargar desde cualquier otro nodo ONLINE
  que lo comparta; si no hay, lo marcamos como no replicable ahora.
- Si se replica, registramos el archivo para que aparezca asociado al nodo central.

Esta versión es básica y no maneja conflictos ni versiones; sirve como primer paso.
"""

from __future__ import annotations

import os
import shutil
import logging
import httpx
from typing import List, Dict

import database
from services.central_service import CENTRAL_NODE_ID, index_central_folder

logger = logging.getLogger("replication")

def _target_folders() -> list[str]:
    """Return list of replication targets.

    - CENTRAL_SHARED_FOLDER (always included)
    - REPLICATION_TARGETS: semicolon-separated absolute or relative paths
    """
    targets = []
    central = os.getenv("CENTRAL_SHARED_FOLDER", "./central_shared")
    targets.append(central)
    extra = os.getenv("REPLICATION_TARGETS", "").strip()
    if extra:
        for p in extra.split(";"):
            p = p.strip()
            if p:
                targets.append(p)
    # ensure existence
    out = []
    for t in targets:
        t_abs = os.path.abspath(t)
        os.makedirs(t_abs, exist_ok=True)
        out.append(t_abs)
    return out

def find_offline_files(limit: int = 100) -> List[Dict]:
    """Devuelve archivos pertenecientes a nodos OFFLINE (máx 'limit')."""
    with database.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT f.* FROM files f
            JOIN nodes n ON n.node_id = f.node_id
            WHERE n.status = 'offline'
            LIMIT ?
            """,
            (limit,)
        )
        return [dict(r) for r in cur.fetchall()]

def get_online_nodes_with_file(file_id: str) -> List[Dict]:
    with database.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT n.* FROM files f
            JOIN nodes n ON n.node_id = f.node_id
            WHERE f.file_id = ? AND n.status = 'online'
            """,
            (file_id,)
        )
        return [dict(r) for r in cur.fetchall()]

def replicate_missing_files(batch: int = 25) -> Dict:
    """Replica algunos archivos de nodos OFFLINE hacia el repositorio central.

    Retorna un resumen con cantidades.
    """
    offline_files = find_offline_files(limit=batch)
    if not offline_files:
        return {"checked": 0, "replicated": 0}

    targets = _target_folders()
    replicated = 0
    for f in offline_files:
        fid = f["file_id"]
        name = f["name"]
        candidates = get_online_nodes_with_file(fid)
        if not candidates:
            continue
        node = candidates[0]
        # Descargar vía endpoint del nodo
        url = f"http://{node['ip_address']}:{node['port']}/files/{fid}"
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(url)
                if resp.status_code != 200:
                    continue
                # Guardar en cada destino manteniendo nombre; evitar colisiones simples
                for dest in targets:
                    out_path = os.path.join(dest, name)
                    base, ext = os.path.splitext(out_path)
                    i = 1
                    while os.path.exists(out_path):
                        out_path = f"{base} ({i}){ext}"
                        i += 1
                    with open(out_path, "wb") as fp:
                        fp.write(resp.content)
                replicated += 1
        except Exception:
            continue

    # Reindexar carpeta central para registrar réplicas
    if replicated:
        try:
            # indexar al menos la carpeta central
            central = os.getenv("CENTRAL_SHARED_FOLDER", "./central_shared")
            index_central_folder(central)
        except Exception:
            pass
    return {"checked": len(offline_files), "replicated": replicated}
