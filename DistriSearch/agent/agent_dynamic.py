#!/usr/bin/env python3
"""
Agente Dinámico - Se registra automáticamente al backend sin configuración previa
"""
import os
import sys
import time
import requests
import argparse
from pathlib import Path
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(f"Agent-{os.getenv('NODE_ID', 'unknown')}")

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
API_KEY = os.getenv("ADMIN_API_KEY", "")
NODE_ID = os.getenv("NODE_ID", f"agent_{int(time.time())}")
SHARED_FOLDER = os.getenv("SHARED_FOLDER", "./shared")
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", "300"))  # 5 minutos

def register_with_backend():
    """Se registra dinámicamente en el backend"""
    try:
        payload = {
            "node_id": NODE_ID,
            "name": f"Agente {NODE_ID}",
            "port": int(os.getenv("FILE_SERVER_PORT", "8080")),
            "auto_scan": True
        }
        
        headers = {}
        if API_KEY:
            headers["X-API-KEY"] = API_KEY
        
        response = requests.post(
            f"{BACKEND_URL}/register/node/dynamic",
            json=payload,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info(f"✅ Registrado exitosamente en {BACKEND_URL}")
            config = response.json().get("data", {})
            return True
        else:
            logger.error(f"❌ Error de registro: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error conectando con backend: {e}")
        return False

def scan_and_report():
    """Escanea la carpeta compartida y reporta archivos"""
    try:
        # Aquí iría tu lógica de escaneo actual
        # Puedes reutilizar el código del agente estático
        logger.info(f"🔍 Escaneando carpeta: {SHARED_FOLDER}")
        
        # Ejemplo simplificado:
        files = []
        for file_path in Path(SHARED_FOLDER).glob("*"):
            if file_path.is_file():
                files.append({
                    "file_id": file_path.name,
                    "name": file_path.name,
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                    "mime_type": "application/octet-stream",
                    "type": "other",
                    "node_id": NODE_ID,
                    "last_updated": datetime.now().isoformat()
                })
        
        if files:
            headers = {"X-API-KEY": API_KEY} if API_KEY else {}
            response = requests.post(
                f"{BACKEND_URL}/register/files",
                json=files,
                headers=headers
            )
            if response.status_code == 200:
                logger.info(f"✅ {len(files)} archivos reportados")
        
    except Exception as e:
        logger.error(f"❌ Error escaneando: {e}")

def send_heartbeat():
    """Envía heartbeat periódico"""
    try:
        headers = {"X-API-KEY": API_KEY} if API_KEY else {}
        requests.post(
            f"{BACKEND_URL}/register/heartbeat/{NODE_ID}",
            headers=headers,
            timeout=5
        )
    except Exception:
        pass

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", help="URL del backend")
    parser.add_argument("--node-id", help="ID del nodo")
    parser.add_argument("--folder", help="Carpeta a compartir")
    args = parser.parse_args()
    
    global BACKEND_URL, NODE_ID, SHARED_FOLDER
    if args.backend: BACKEND_URL = args.backend
    if args.node_id: NODE_ID = args.node_id
    if args.folder: SHARED_FOLDER = args.folder
    
    # 1. Registrar nodo
    if not register_with_backend():
        sys.exit(1)
    
    # 2. Loop principal
    while True:
        try:
            send_heartbeat()
            scan_and_report()
            time.sleep(SCAN_INTERVAL)
        except KeyboardInterrupt:
            logger.info("🛑 Agent stopped")
            break
        except Exception as e:
            logger.error(f"❌ Error en loop: {e}")
            time.sleep(60)  # Esperar antes de reintentar

if __name__ == "__main__":
    main()