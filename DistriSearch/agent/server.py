from aiohttp import web
import os
import logging
import hashlib
import ssl

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
    Inicia el servidor HTTP/HTTPS para servir archivos
    """
    app = web.Application()
    app['shared_folder'] = shared_folder
    # Build initial cache
    _build_cache(shared_folder)
    
    # Rutas
    app.router.add_get('/status', handle_status)
    app.router.add_get('/files/{file_id}', handle_file_download)
    
    # Configuración SSL/TLS
    ssl_enabled = os.getenv("AGENT_SSL_ENABLED", "false").lower() in {"true", "1", "yes"}
    ssl_context = None
    
    if ssl_enabled:
        ssl_certfile = os.getenv("AGENT_SSL_CERT_FILE", "../certs/distrisearch.crt")
        ssl_keyfile = os.getenv("AGENT_SSL_KEY_FILE", "../certs/distrisearch.key")
        
        if os.path.exists(ssl_certfile) and os.path.exists(ssl_keyfile):
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(ssl_certfile, ssl_keyfile)
            logger.info(f"SSL habilitado con certificado: {ssl_certfile}")
        else:
            logger.warning(f"SSL habilitado pero certificados no encontrados. Usando HTTP.")
            logger.warning(f"Certificado esperado: {ssl_certfile}")
            logger.warning(f"Clave esperada: {ssl_keyfile}")
    
    # Iniciar servidor
    protocol = "HTTPS" if ssl_context else "HTTP"
    logger.info(f"Iniciando servidor de archivos {protocol} en puerto {port}")
    
    web.run_app(app, host='0.0.0.0', port=port, ssl_context=ssl_context)
