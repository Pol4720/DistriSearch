import os
import sys
import socket
import threading
import requests
import logging

logger = logging.getLogger(__name__)


class DHTService:
    """Wrapper para la implementación DHT local o remota.

    Modo configurable vía env DHT_MODE: 'external' (llama HTTP) o 'inproc' (importa Peer).
    """

    def __init__(self):
        self.mode = os.getenv("DHT_MODE", "external")
        self.external_url = os.getenv("DHT_HTTP_URL", "http://127.0.0.1:8080")
        self.peer = None

        # Parámetros para modo inproc
        self.port = int(os.getenv("DHT_PORT", "2000"))
        self.buffer = int(os.getenv("DHT_BUFFER", "4096"))
        self.max_bits = int(os.getenv("DHT_MAX_BITS", "10"))

    def start(self):
        if self.mode == "inproc":
            # Iniciar Peer en proceso actual
            try:
                # Añadir la carpeta raíz del proyecto al PYTHONPATH para poder importar DHT
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
                if project_root not in sys.path:
                    sys.path.insert(0, project_root)
                    logger.info("📦 Añadido al PYTHONPATH: %s", project_root)
                
                from DHT.peer import Peer

                # Determinar IP local
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                s.close()

                self.peer = Peer(ip, self.port, self.buffer, self.max_bits)
                self.peer.start()
                logger.info("✅ DHT inproc: Peer iniciado en %s:%s (ID: %s)", ip, self.port, self.peer.id)
            except Exception as exc:
                logger.exception("❌ Error iniciando DHT inproc: %s", exc)
                raise
        else:
            logger.info("🌐 DHT mode external: usando %s", self.external_url)

    # --- Common operations ---
    def join(self, seed_ip: str, seed_port: int = None):
        if self.mode == "inproc":
            if not self.peer:
                raise RuntimeError("Peer no iniciado")
            if seed_port is None:
                seed_port = self.port
            return self.peer.unirseRed(seed_ip, seed_port)
        else:
            params = {"ip": seed_ip}
            if seed_port:
                params["port"] = seed_port
            resp = requests.get(f"{self.external_url}/server/rest/DHT/addNode", params=params, timeout=5)
            resp.raise_for_status()
            return resp.text

    def upload(self, filename: str, data: str):
        if self.mode == "inproc":
            if not self.peer:
                raise RuntimeError("Peer no iniciado")
            return self.peer.subirFichero(filename, data, self.peer.sucesor, True)
        else:
            params = {"filename": filename, "data": data}
            resp = requests.get(f"{self.external_url}/server/rest/DHT/uploadContent", params=params, timeout=10)
            resp.raise_for_status()
            return resp.text

    def download(self, filename: str):
        if self.mode == "inproc":
            if not self.peer:
                raise RuntimeError("Peer no iniciado")
            return self.peer.descargarFichero(filename)
        else:
            params = {"filename": filename}
            resp = requests.get(f"{self.external_url}/server/rest/DHT/downloadContent", params=params, timeout=10)
            resp.raise_for_status()
            return resp.text

    def finger_table(self):
        if self.mode == "inproc":
            if not self.peer:
                return {}
            return {k: v for k, v in self.peer.fingerTable.items()}
        else:
            resp = requests.get(f"{self.external_url}/server/rest/DHT/imprimirFingerTable", timeout=5)
            resp.raise_for_status()
            return resp.text

    def suc_pred(self):
        if self.mode == "inproc":
            if not self.peer:
                return {}
            return {"id": self.peer.id, "sucesor": self.peer.sucesor, "predecesor": self.peer.predecesor}
        else:
            resp = requests.get(f"{self.external_url}/server/rest/DHT/imprimirSucPred", timeout=5)
            resp.raise_for_status()
            return resp.text


# Singleton
service = DHTService()
