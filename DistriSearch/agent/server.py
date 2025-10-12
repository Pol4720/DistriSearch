from aiohttp import web
import os
import logging
import hashlib

logger = logging.getLogger('file_server')

_CACHE = {}

def _build_cache(shared_folder: str):
    global _CACHE
    _CACHE = {}
    for root, _, files in os.walk(shared_folder):
        for filename in files:
            path = os.path.join(root, filename)
            try:
                hasher = hashlib.sha256()
                with open(path, 'rb') as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        hasher.update(chunk)
                _CACHE[hasher.hexdigest()] = path
            except Exception:
                continue

async def handle_file_download(request):
    """
    Maneja descargas de archivos
    """
    file_id = request.match_info.get('file_id')
    shared_folder = request.app['shared_folder']
    
    # Buscar el archivo por su hash (file_id) usando cache y, si no, refrescar
    found_file = _CACHE.get(file_id)
    if not found_file:
        _build_cache(shared_folder)
        found_file = _CACHE.get(file_id)
    
    if not found_file:
        return web.Response(status=404, text="Archivo no encontrado")
    
    # Preparar la respuesta para la descarga
    response = web.FileResponse(
        path=found_file,
        headers={
            'Content-Disposition': f'attachment; filename="{os.path.basename(found_file)}"'
        }
    )
    
    logger.info(f"Enviando archivo: {found_file}")
    return response

async def handle_status(request):
    """
    Endpoint para verificar el estado del servidor
    """
    return web.json_response({"status": "online"})

def start_file_server(shared_folder, port):
    """
    Inicia el servidor HTTP para servir archivos
    """
    app = web.Application()
    app['shared_folder'] = shared_folder
    # Build initial cache
    _build_cache(shared_folder)
    
    # Rutas
    app.router.add_get('/status', handle_status)
    app.router.add_get('/files/{file_id}', handle_file_download)
    
    # Iniciar servidor
    logger.info(f"Iniciando servidor de archivos en puerto {port}")
    web.run_app(app, host='0.0.0.0', port=port)
