from fastapi import APIRouter, HTTPException, Body
from fastapi import Depends, Request, File, UploadFile, Form
from typing import List, Optional
from models import FileMeta, NodeInfo, NodeRegistration
from services import index_service, node_service
from datetime import datetime
from security import require_api_key
import database
import os
import mimetypes
import hashlib
import logging
from services.dynamic_replication import get_replication_service 

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/register",
    tags=["register"],
    responses={404: {"description": "Not found"}},
)

@router.post("/node")
async def register_node(node: NodeInfo = Body(...), _: None = Depends(require_api_key)):
    """Registra un nuevo nodo en el sistema o actualiza uno existente"""
    return node_service.register_node(node)

@router.post("/files")
async def register_files(files: List[FileMeta] = Body(...)):
    """Registra metadatos de archivos desde un nodo"""
    try:
        result = index_service.register_files(files)
        return {"status": "success", "indexed_count": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/heartbeat/{node_id}")
async def node_heartbeat(node_id: str):
    """Actualiza el estado y timestamp de última conexión del nodo"""
    success = node_service.update_node_heartbeat(node_id)
    if not success:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"status": "online"}

@router.delete("/node/{node_id}")
async def delete_node(node_id: str, delete_files: bool = True, _: None = Depends(require_api_key)):
    """Elimina un nodo del sistema."""
    existing = database.get_node(node_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Node not found")

    # Usar MongoDB
    import os
    from pymongo import MongoClient
    
    client = MongoClient(os.getenv("MONGO_URI"))
    db = client[os.getenv("MONGO_DBNAME", "distrisearch")]
    
    if delete_files:
        db.files.delete_many({"node_id": node_id})
        # Limpiar contenidos huérfanos
        file_ids = [f["file_id"] for f in db.files.find({}, {"file_id": 1})]
        db.file_contents.delete_many({"file_id": {"$nin": file_ids}})
    
    db.nodes.delete_one({"node_id": node_id})
    
    return {"status": "deleted", "node_id": node_id, "deleted_files": delete_files}

@router.post("/node/{node_id}/mount")
async def set_node_folder(node_id: str, folder: str = Body(..., embed=True), _: None = Depends(require_api_key)):
    """Configura una carpeta local asociada a un nodo."""
    if not database.get_node(node_id):
        raise HTTPException(status_code=404, detail="Node not found")
    database.set_node_mount(node_id, folder)
    database.update_node_status(node_id, "online")
    return {"status": "ok", "node_id": node_id, "folder": os.path.abspath(folder)}

@router.post("/node/{node_id}/scan-import")
async def import_from_node_folder(node_id: str, _: None = Depends(require_api_key)):
    """Escanea la carpeta montada del nodo y registra archivos."""
    mount = database.get_node_mount(node_id)
    if not mount:
        raise HTTPException(status_code=400, detail="Node folder not configured")
    
    abspath = os.path.abspath(mount)
    mimetypes.init()
    count = 0
    
    for root, _, files in os.walk(abspath):
        for fname in files:
            full = os.path.join(root, fname)
            try:
                mime, _ = mimetypes.guess_type(full)
                if not mime:
                    mime = 'application/octet-stream'
                rel = os.path.relpath(full, abspath)
                
                # Determinar tipo
                if mime.startswith('image'):
                    file_type = 'image'
                elif mime.startswith('video'):
                    file_type = 'video'
                elif mime.startswith('audio'):
                    file_type = 'audio'
                elif mime.startswith('text') or 'document' in mime:
                    file_type = 'document'
                else:
                    file_type = 'other'
                
                fm = FileMeta(
                    file_id=f"{node_id}_{hashlib.md5(rel.encode()).hexdigest()}",
                    name=fname,
                    path=rel,
                    size=os.path.getsize(full),
                    mime_type=mime,
                    type=file_type,
                    node_id=node_id,
                    last_updated=datetime.fromtimestamp(os.path.getmtime(full)),
                    content_hash=None  # Opcional
                )
                database.register_file(fm)
                count += 1
            except Exception as e:
                logger.warning(f"Error procesando {full}: {e}")
                continue
    
    database.update_node_status(node_id, "online")
    total = database.get_node_file_count(node_id)
    database.update_node_shared_files_count(node_id, total)
    
    return {"status": "ok", "imported": count, "folder": abspath, "node_files": total}

@router.post("/node/{node_id}/sync")
async def sync_node_folder(node_id: str, _: None = Depends(require_api_key)):
    """Sincroniza el estado completo del nodo con su carpeta montada."""
    mount = database.get_node_mount(node_id)
    if not mount:
        raise HTTPException(status_code=400, detail="Node folder not configured")
    
    abspath = os.path.abspath(mount)
    mimetypes.init()
    
    current_ids = set()
    imported = 0
    
    # Escanear archivos actuales
    for root, _, files in os.walk(abspath):
        for fname in files:
            full = os.path.join(root, fname)
            try:
                mime, _ = mimetypes.guess_type(full)
                if not mime:
                    mime = 'application/octet-stream'
                rel = os.path.relpath(full, abspath)
                fid = f"{node_id}_{hashlib.md5(rel.encode()).hexdigest()}"
                current_ids.add(fid)
                
                # Determinar tipo
                if mime.startswith('image'):
                    file_type = 'image'
                elif mime.startswith('video'):
                    file_type = 'video'
                elif mime.startswith('audio'):
                    file_type = 'audio'
                elif mime.startswith('text') or 'document' in mime:
                    file_type = 'document'
                else:
                    file_type = 'other'
                
                fm = FileMeta(
                    file_id=fid,
                    name=fname,
                    path=rel,
                    size=os.path.getsize(full),
                    mime_type=mime,
                    type=file_type,
                    node_id=node_id,
                    last_updated=datetime.fromtimestamp(os.path.getmtime(full))
                )
                database.register_file(fm)
                imported += 1
            except Exception:
                continue
    
    # Eliminar archivos obsoletos de la DB
    import os
    from pymongo import MongoClient
    
    client = MongoClient(os.getenv("MONGO_URI"))
    db = client[os.getenv("MONGO_DBNAME", "distrisearch")]
    
    existing_files = list(db.files.find({"node_id": node_id}, {"file_id": 1}))
    existing_ids = {f["file_id"] for f in existing_files}
    stale = list(existing_ids - current_ids)
    
    if stale:
        db.files.delete_many({"node_id": node_id, "file_id": {"$in": stale}})
        file_ids = [f["file_id"] for f in db.files.find({}, {"file_id": 1})]
        db.file_contents.delete_many({"file_id": {"$nin": file_ids}})
    
    database.update_node_status(node_id, "online")
    total = database.get_node_file_count(node_id)
    database.update_node_shared_files_count(node_id, total)
    
    return {"status": "ok", "imported": imported, "removed": len(stale), "folder": abspath, "node_files": total}


# register.py - Agregar nuevo endpoint

@router.post("/node/dynamic")
async def register_node_dynamic_endpoint(
    registration: NodeRegistration,
    request: Request
):
    """Registro dinámico de nodos. Los nodos pueden autoregistrarse sin configuración previa."""
    try:
        # Autodetectar IP desde la petición
        client_host = request.client.host if request.client else None
        
        result = node_service.register_node_dynamic(
            node_id=registration.node_id,
            name=registration.name,
            ip_address=registration.ip_address,
            port=registration.port,
            request_host=client_host,
            shared_folder=registration.shared_folder
        )
        
        return {
            "status": "success",
            "data": result,
            "config_endpoint": f"{request.base_url}register/node/{registration.node_id}/config"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en registro dinámico: {str(e)}")

@router.get("/node/{node_id}/config")
async def get_node_configuration(node_id: str):
    """Endpoint para que los nodos obtengan su configuración completa después de registrarse."""
    config = node_service.get_node_config(node_id)
    if not config:
        raise HTTPException(status_code=404, detail="Nodo no encontrado")
    
    return {
        "status": "success",
        "config": config
    }

# ✅ NUEVO: Endpoint para subir archivos directamente
@router.post("/upload")
async def upload_file_to_system(
    file: UploadFile = File(...),
    node_id: Optional[str] = Form(None),  # Usa NODE_ID del entorno si no se especifica
    virtual_path: Optional[str] = Form(None),
    replicate: Optional[str] = Form("false"),
    _: None = Depends(require_api_key)
):
    """
    Sube un archivo al sistema.
    Si replicate=true, automáticamente lo replica a otros nodos.
    """
    # Usar NODE_ID del entorno si no se especifica
    if not node_id:
        node_id = os.getenv("NODE_ID", "node_1")
    
    try:
        # Leer contenido del archivo
        content = await file.read()
        
        # Validar tamaño
        max_size = 100 * 1024 * 1024  # 100 MB
        if len(content) > max_size:
            raise HTTPException(status_code=413, detail=f"Archivo muy grande (max: {max_size} bytes)")
        
        # Determinar ruta de almacenamiento
        node = database.get_node(node_id)
        if not node:
            raise HTTPException(status_code=404, detail=f"Nodo {node_id} no encontrado")
        
        # Crear directorio del nodo si no existe
        uploads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads", node_id))
        os.makedirs(uploads_dir, exist_ok=True)
        
        # Guardar archivo
        file_path = os.path.join(uploads_dir, file.filename)
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Calcular hash
        content_hash = hashlib.sha256(content).hexdigest()
        
        # Generar file_id único
        file_id = f"{node_id}_{content_hash[:16]}"
        
        # Determinar tipo de archivo
        mime_type = file.content_type or "application/octet-stream"
        
        if mime_type.startswith("image/"):
            file_type = "image"
        elif mime_type.startswith("video/"):
            file_type = "video"
        elif mime_type.startswith("audio/"):
            file_type = "audio"
        elif mime_type in ["application/pdf", "application/msword", "text/plain"]:
            file_type = "document"
        else:
            file_type = "other"
        
        # Crear metadata
        file_meta = FileMeta(
            file_id=file_id,
            name=file.filename,
            path=virtual_path or f"/{file.filename}",
            size=len(content),
            mime_type=mime_type,
            type=file_type,
            node_id=node_id,
            last_updated=datetime.utcnow(),
            content_hash=content_hash
        )
        
        # Registrar en base de datos
        database.register_file(file_meta)
        
        logger.info(f"✅ Archivo subido: {file_id} ({len(content)} bytes)")
        
        # ✅ ARREGLO CRÍTICO: Siempre intentar replicar si está habilitado
        replication_result = None
        should_replicate = replicate.lower() in {"true", "1", "yes"}
        
        if should_replicate:
            try:
                repl_service = get_replication_service()
                
                # Convertir FileMeta a dict
                file_dict = {
                    "file_id": file_meta.file_id,
                    "name": file_meta.name,
                    "path": file_meta.path,
                    "size": file_meta.size,
                    "mime_type": file_meta.mime_type,
                    "type": file_meta.type,
                    "node_id": file_meta.node_id,
                    "content_hash": file_meta.content_hash,
                    "physical_path": file_path,  # ✅ CRÍTICO: Pasar ruta física
                    "last_updated": datetime.utcnow()
                }
                
                # ✅ ESPERAR LA REPLICACIÓN (no fire-and-forget)
                replication_result = await repl_service.replicate_file(
                    file_dict,
                    source_node_id=node_id
                )
                
                logger.info(f"🔄 Replicación completa: {replication_result}")
                
            except Exception as e:
                logger.error(f"⚠️ Error en replicación: {e}", exc_info=True)
                # ✅ IMPORTANTE: Informar del error pero no fallar el upload
        
        return {
            "status": "success",
            "file_id": file_id,
            "filename": file.filename,
            "size": len(content),
            "node_id": node_id,
            "content_hash": content_hash,
            "path": file_path,
            "replicated": replication_result is not None,
            "replication_info": replication_result
        }
        
    except Exception as e:
        logger.error(f"❌ Error subiendo archivo: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload/bulk")
async def upload_multiple_files(
    files: List[UploadFile] = File(...),
    node_id: Optional[str] = Form(None),  # Usa NODE_ID del entorno si no se especifica
    _: None = Depends(require_api_key)
):
    """Sube múltiples archivos de una vez"""
    # Usar NODE_ID del entorno si no se especifica
    if not node_id:
        node_id = os.getenv("NODE_ID", "node_1")
    
    results = []
    
    for file in files:
        try:
            result = await upload_file_to_system(file, node_id, None, None)
            results.append(result)
        except Exception as e:
            results.append({
                "filename": file.filename,
                "status": "error",
                "error": str(e)
            })
    
    successful = sum(1 for r in results if r.get("status") == "success")
    
    return {
        "total": len(files),
        "successful": successful,
        "failed": len(files) - successful,
        "results": results
    }