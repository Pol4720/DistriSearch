#!/usr/bin/env python3
"""
migrate_sqlite_to_mongo.py

Migra datos desde una base SQLite hacia MongoDB + GridFS (opcional).
- Crea índices mínimos en Mongo.
- Inserta/upserta documentos en colecciones: files, file_contents, nodes, node_mounts.
- Guarda contenidos largos en GridFS (por file_id como filename).
- Soporta --dry-run (no escribe), --batch-size y --skip-tables.
"""

import os
import sys
import sqlite3
import argparse
from datetime import datetime
from typing import Dict, Any, List, Optional

try:
    from pymongo import MongoClient, ASCENDING, TEXT, UpdateOne
    import gridfs
except Exception as e:
    print("ERROR: necesitas instalar pymongo: pip install pymongo")
    raise

# ------- Config / Defaults -------
DEFAULT_SQLITE = os.getenv("SQLITE_DB", "distrisearch.db")
DEFAULT_MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DEFAULT_MONGO_DB = os.getenv("MONGO_DBNAME", "distrisearch")
GRIDFS_THRESHOLD = int(os.getenv("GRIDFS_THRESHOLD_BYTES", "200000"))  # 200 KB

# ------- Helpers -------
def iso_or_unix_to_dt(val) -> Optional[datetime]:
    """Intenta convertir valores comunes de sqlite a datetime."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, (int, float)):
        # interpretar como timestamp (segundos)
        try:
            return datetime.fromtimestamp(int(val))
        except Exception:
            return None
    s = str(val).strip()
    if not s:
        return None
    # intentar ISO
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    # intentar como entero string (timestamp)
    try:
        iv = int(s)
        return datetime.fromtimestamp(iv)
    except Exception:
        pass
    return None

def get_sqlite_tables(conn: sqlite3.Connection) -> List[str]:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return [r[0] for r in cur.fetchall()]

def get_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return [r[1] for r in cur.fetchall()]

def row_to_dict(cursor: sqlite3.Cursor, row: sqlite3.Row) -> Dict[str, Any]:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

# ------- Migration logic -------
class Migrator:
    def __init__(self, sqlite_path: str, mongo_uri: str, mongo_dbname: str,
                 dry_run: bool = False, batch_size: int = 500, gridfs_threshold: int = GRIDFS_THRESHOLD):
        self.sqlite_path = sqlite_path
        self.mongo_uri = mongo_uri
        self.mongo_dbname = mongo_dbname
        self.dry_run = dry_run
        self.batch_size = batch_size
        self.gridfs_threshold = gridfs_threshold

        # sqlite connection
        self.sconn = sqlite3.connect(self.sqlite_path)
        self.sconn.row_factory = sqlite3.Row

        # mongo connection
        self.mclient = MongoClient(self.mongo_uri)
        self.mdb = self.mclient[self.mongo_dbname]
        self.fs = gridfs.GridFS(self.mdb)

        # stats
        self.stats = {"files": 0, "file_contents": 0, "nodes": 0, "node_mounts": 0, "errors": 0}

    def ensure_indexes(self):
        print("Creando índices en Mongo (si no existen)...")
        try:
            self.mdb.files.create_index([("file_id", ASCENDING), ("node_id", ASCENDING)], unique=True, name="u_file_node")
            self.mdb.files.create_index([("node_id", ASCENDING), ("path", ASCENDING)], unique=True, name="u_node_path")
            self.mdb.file_contents.create_index([("name", TEXT), ("content", TEXT)], name="text_name_content",
                                               default_language="spanish", weights={"name": 10, "content": 1})
            self.mdb.nodes.create_index([("node_id", ASCENDING)], unique=True, name="u_node_id")
            self.mdb.node_mounts.create_index([("node_id", ASCENDING)], unique=True, name="u_node_mount")
            self.mdb.files.create_index([("content_hash", ASCENDING)], name="idx_files_content_hash")
        except Exception as e:
            print("Advertencia creando índices:", e)

    def _store_gridfs(self, file_id: str, content_bytes: bytes) -> str:
        # elimina versiones previas con filename=file_id para reemplazo
        prev = self.mdb.fs.files.find_one({"filename": file_id})
        if prev:
            try:
                self.mdb.fs.files.delete_one({"_id": prev["_id"]})
                self.mdb.fs.chunks.delete_many({"files_id": prev["_id"]})
            except Exception:
                pass
        gfid = self.fs.put(content_bytes, filename=file_id)
        return str(gfid)

    def migrate_table(self, table: str, target: str, transform_fn=None, key_cols: Optional[List[str]] = None):
        """
        Migra filas de `table` (sqlite) a `target` (mongo).
        - transform_fn(row_dict) -> document_dict
        - key_cols: columnas para usar en upsert filter (si None, intenta usar file_id/node_id heurística)
        """
        s_cur = self.sconn.cursor()
        try:
            s_cur.execute(f"SELECT COUNT(*) FROM {table}")
            total = s_cur.fetchone()[0]
        except Exception as e:
            print(f"No se puede leer tabla {table}: {e}")
            return

        print(f"Migrando tabla {table} -> {target} (filas: {total})")
        s_cur.execute(f"SELECT * FROM {table}")
        batch: List[UpdateOne] = []
        processed = 0
        while True:
            rows = s_cur.fetchmany(self.batch_size)
            if not rows:
                break
            for r in rows:
                try:
                    row = dict(r)
                    doc = transform_fn(row) if transform_fn else row
                    # normalizar datetimes: busca claves comunes y conviértelas
                    if isinstance(doc, dict):
                        for date_key in ("last_updated", "updated_at", "created_at", "last_seen"):
                            if date_key in doc:
                                dt = iso_or_unix_to_dt(doc[date_key])
                                if dt:
                                    doc[date_key] = dt
                    # determinar filtro de upsert
                    if key_cols:
                        filt = {k: doc.get(k) for k in key_cols}
                    else:
                        # heurística: if file_id and node_id exist
                        if "file_id" in doc and "node_id" in doc:
                            filt = {"file_id": doc["file_id"], "node_id": doc["node_id"]}
                        elif "file_id" in doc:
                            filt = {"file_id": doc["file_id"]}
                        elif "node_id" in doc:
                            filt = {"node_id": doc["node_id"]}
                        else:
                            # si no hay key identificable, usar _id autogenerado (insert)
                            filt = None

                    if self.dry_run:
                        # solo contamos
                        self.stats[target] = self.stats.get(target, 0) + 1
                    else:
                        if filt:
                            batch.append(UpdateOne(filt, {"$set": doc}, upsert=True))
                        else:
                            # insert simple
                            batch.append(UpdateOne({"_tmp_auto_id": doc.get("_tmp_auto_id", None) or {"$exists": False}},
                                                   {"$setOnInsert": doc}, upsert=True))
                except Exception as e:
                    print("Error procesando fila:", e)
                    self.stats["errors"] += 1

                processed += 1
                # ejecutar batch si alcanzado
                if not self.dry_run and len(batch) >= self.batch_size:
                    try:
                        result = getattr(self.mdb[target], "bulk_write")(batch, ordered=False)
                        # opcional: podríamos loggear result.bulk_api_result
                    except Exception as e:
                        print("Error en bulk_write:", e)
                        self.stats["errors"] += 1
                    batch = []

            print(f"  Procesadas {processed}/{total}", end="\r", flush=True)

        # ejecutar batch restante
        if not self.dry_run and batch:
            try:
                getattr(self.mdb[target], "bulk_write")(batch, ordered=False)
            except Exception as e:
                print("Error en bulk_write final:", e)
                self.stats["errors"] += 1

        print(f"\n  Completado {table} -> {target}: procesadas {processed}")

    def migrate_files_with_contents(self, files_table: str = "files", file_contents_table: str = "file_contents"):
        """
        Migración más cuidadosa para files + file_contents:
        - Recorre files; intenta buscar contenido en file_contents por file_id.
        - Si content > threshold -> guarda en GridFS y añade gridfs_id en file_contents doc.
        - Upserta en mdb.files y mdb.file_contents.
        """
        s_cur = self.sconn.cursor()
        try:
            s_cur.execute(f"SELECT COUNT(*) FROM {files_table}")
            total = s_cur.fetchone()[0]
        except Exception as e:
            print(f"No se puede leer tabla {files_table}: {e}")
            return

        s_cur.execute(f"SELECT * FROM {files_table}")
        processed = 0
        batch_files: List[UpdateOne] = []
        batch_file_contents: List[UpdateOne] = []
        print(f"Migrando files ({total})...")
        while True:
            rows = s_cur.fetchmany(self.batch_size)
            if not rows:
                break
            for r in rows:
                frow = dict(r)
                try:
                    file_id = frow.get("file_id") or frow.get("id") or frow.get("uuid") or frow.get("name")
                    # build document for files collection
                    fdoc = dict(frow)  # shallow copy
                    # convert common timestamps
                    for k in ("last_updated","updated_at","created_at"):
                        if k in fdoc:
                            dt = iso_or_unix_to_dt(fdoc[k])
                            if dt:
                                fdoc[k] = dt
                    if not file_id:
                        file_id = fdoc.get("path") or fdoc.get("name")
                    fdoc["file_id"] = file_id

                    # find content in sqlite file_contents table
                    content_snippet = None
                    gridfs_id = None
                    try:
                        ccur = self.sconn.cursor()
                        ccur.execute(f"SELECT * FROM {file_contents_table} WHERE file_id = ?", (file_id,))
                        crow = ccur.fetchone()
                        if crow:
                            cdoc = dict(crow)
                            raw = cdoc.get("content") or cdoc.get("body") or cdoc.get("text")
                            if raw is not None:
                                if isinstance(raw, str):
                                    raw_bytes = raw.encode("utf-8")
                                elif isinstance(raw, (bytes, bytearray)):
                                    raw_bytes = bytes(raw)
                                else:
                                    raw_bytes = str(raw).encode("utf-8")
                                if len(raw_bytes) > self.gridfs_threshold:
                                    # store gridfs
                                    if not self.dry_run:
                                        gridfs_id = self._store_gridfs(file_id, raw_bytes)
                                    content_snippet = raw_bytes[:200000].decode("utf-8", errors="ignore")
                                else:
                                    content_snippet = raw_bytes.decode("utf-8", errors="ignore")
                            # merge other metadata from cdoc into file_contents doc
                            file_contents_doc = {"file_id": file_id,
                                                 "name": cdoc.get("name") or fdoc.get("name"),
                                                 "content": content_snippet or "",
                                                 "gridfs_id": gridfs_id}
                        else:
                            file_contents_doc = {"file_id": file_id, "name": fdoc.get("name"), "content": ""}
                    except Exception as e:
                        print("  warning buscando content for", file_id, ":", e)
                        file_contents_doc = {"file_id": file_id, "name": fdoc.get("name"), "content": ""}

                    # prepare upserts
                    # files upsert key: file_id + node_id if node_id exists
                    if "node_id" in fdoc and fdoc.get("node_id") is not None:
                        filt_files = {"file_id": file_id, "node_id": fdoc.get("node_id")}
                    else:
                        filt_files = {"file_id": file_id}
                    if self.dry_run:
                        self.stats["files"] += 1
                        self.stats["file_contents"] += 1
                    else:
                        batch_files.append(UpdateOne(filt_files, {"$set": fdoc}, upsert=True))
                        batch_file_contents.append(UpdateOne({"file_id": file_id}, {"$set": file_contents_doc}, upsert=True))
                except Exception as e:
                    print("Error migrando file row:", e)
                    self.stats["errors"] += 1
                processed += 1

                if not self.dry_run and len(batch_files) >= self.batch_size:
                    try:
                        self.mdb.files.bulk_write(batch_files, ordered=False)
                        self.mdb.file_contents.bulk_write(batch_file_contents, ordered=False)
                    except Exception as e:
                        print("bulk_write error:", e)
                        self.stats["errors"] += 1
                    batch_files, batch_file_contents = [], []

            print(f"  Procesadas {processed}/{total}", end="\r", flush=True)

        if not self.dry_run:
            if batch_files:
                try:
                    self.mdb.files.bulk_write(batch_files, ordered=False)
                    self.mdb.file_contents.bulk_write(batch_file_contents, ordered=False)
                except Exception as e:
                    print("bulk_write final error:", e)
                    self.stats["errors"] += 1

        print(f"\n  Completado files migration. Procesadas: {processed}")

    def migrate_nodes(self, table_name: str = "nodes"):
        def transform(nrow: Dict[str, Any]) -> Dict[str, Any]:
            doc = dict(nrow)
            # normalizar ints
            for k in ("port", "shared_files_count"):
                if k in doc:
                    try:
                        doc[k] = int(doc[k])
                    except Exception:
                        pass
            # try to coerce last_seen
            for k in ("last_seen","last_seen_at"):
                if k in doc:
                    dt = iso_or_unix_to_dt(doc[k])
                    if dt:
                        doc["last_seen"] = dt
            if "node_id" not in doc:
                doc["node_id"] = doc.get("id") or doc.get("name")
            return doc

        self.migrate_table(table_name, "nodes", transform_fn=transform, key_cols=["node_id"])

    def migrate_node_mounts(self, table_name: str = "node_mounts"):
        def transform(mrow: Dict[str, Any]) -> Dict[str, Any]:
            doc = dict(mrow)
            if "node_id" not in doc:
                doc["node_id"] = doc.get("id") or doc.get("name")
            return doc
        self.migrate_table(table_name, "node_mounts", transform_fn=transform, key_cols=["node_id"])

    def run(self, tables_to_skip: Optional[List[str]] = None):
        if tables_to_skip is None:
            tables_to_skip = []

        print("Conectando a SQLite:", self.sqlite_path)
        print("Conectando a MongoDB:", self.mongo_uri)
        self.ensure_indexes()

        # Intentar migrar files+file_contents con handler especial si existen
        sqlite_tables = get_sqlite_tables(self.sconn)
        print("Tablas detectadas en sqlite:", sqlite_tables)

        if "files" in sqlite_tables and "files" not in tables_to_skip:
            if "file_contents" in sqlite_tables and "file_contents" not in tables_to_skip:
                self.migrate_files_with_contents("files", "file_contents")
            else:
                # fallback simple migrate files
                self.migrate_table("files", "files", key_cols=["file_id", "node_id"])
        else:
            print("No se encontró tabla 'files' en SQLite. Saltando.")

        if "nodes" in sqlite_tables and "nodes" not in tables_to_skip:
            self.migrate_nodes("nodes")
        else:
            print("No se encontró tabla 'nodes' o fue saltada.")

        if "node_mounts" in sqlite_tables and "node_mounts" not in tables_to_skip:
            self.migrate_node_mounts("node_mounts")
        else:
            print("No se encontró tabla 'node_mounts' o fue saltada.")

        # Si hay tabla file_contents suelta (no relacionada) migrarla también
        if "file_contents" in sqlite_tables and "file_contents" not in tables_to_skip:
            # si ya migramos a través de files_with_contents, evitamos doble conteo
            # pero no podemos saber con certeza; intentamos migrar any remaining rows by upsert
            print("Verificando migración directa de file_contents (filas sueltas)...")
            self.migrate_table("file_contents", "file_contents", key_cols=["file_id"])

        print("Migración finalizada.")
        print("Resumen:", self.stats)


# ------- CLI -------
def parse_args():
    p = argparse.ArgumentParser(description="Migra SQLite -> MongoDB (GridFS opcional).")
    p.add_argument("--sqlite", "-s", default=DEFAULT_SQLITE, help="Ruta a la base SQLite")
    p.add_argument("--mongo", "-m", default=DEFAULT_MONGO_URI, help="URI de MongoDB")
    p.add_argument("--db", "-d", default=DEFAULT_MONGO_DB, help="Nombre de la BD Mongo destino")
    p.add_argument("--dry-run", action="store_true", help="No escribe en Mongo; solo muestra lo que haría")
    p.add_argument("--batch-size", type=int, default=500, help="Tamaño de batch para bulk writes")
    p.add_argument("--gridfs-threshold", type=int, default=GRIDFS_THRESHOLD, help="Umbral (bytes) para usar GridFS")
    p.add_argument("--skip", nargs="*", default=[], help="List of sqlite table names to skip")
    return p.parse_args()

def main():
    args = parse_args()
    migrator = Migrator(sqlite_path=args.sqlite, mongo_uri=args.mongo, mongo_dbname=args.db,
                        dry_run=args.dry_run, batch_size=args.batch_size, gridfs_threshold=args.gridfs_threshold)
    migrator.run(tables_to_skip=args.skip)

if __name__ == "__main__":
    main()
