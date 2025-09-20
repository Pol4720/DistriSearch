import time
import threading
import requests
import yaml
import logging
import os
import signal
import sys
from scanner import FileScanner
from uploader import MetadataUploader
from server import start_file_server

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('agent')

class Agent:
    def __init__(self, config_path="config.yaml"):
        # Cargar configuración
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Inicializar componentes
        self.scanner = FileScanner(self.config['shared_folder'])
        self.uploader = MetadataUploader(
            self.config['backend_url'],
            self.config['node_id'],
            self.config['node_name']
        )
        
        # Flags de control
        self.running = False
        self.server_thread = None
        self.scan_thread = None
        self.heartbeat_thread = None
    
    def start(self):
        """Inicia el agente y sus componentes"""
        logger.info(f"Iniciando agente {self.config['node_id']} - {self.config['node_name']}")
        self.running = True
        
        # Registrar el nodo en el backend
        self._register_node()
        
        # Iniciar servidor de archivos
        self.server_thread = threading.Thread(
            target=start_file_server,
            args=(self.config['shared_folder'], self.config['server_port'])
        )
        self.server_thread.daemon = True
        self.server_thread.start()
        logger.info(f"Servidor de archivos iniciado en puerto {self.config['server_port']}")
        
        # Iniciar escaneo inicial y programar escaneos periódicos
        self._start_scanning()
        
        # Iniciar heartbeats
        self._start_heartbeats()
        
        # Escuchar señales para detener limpiamente
        signal.signal(signal.SIGINT, self._handle_exit)
        signal.signal(signal.SIGTERM, self._handle_exit)
        
        try:
            # Mantener el proceso principal vivo
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        """Detiene el agente y sus componentes"""
        logger.info("Deteniendo agente...")
        self.running = False
        # Los threads son daemon, así que terminarán automáticamente
        logger.info("Agente detenido")
    
    def _register_node(self):
        """Registra el nodo en el backend"""
        try:
            node_info = {
                "node_id": self.config['node_id'],
                "name": self.config['node_name'],
                "ip_address": self.config['node_ip'],
                "port": self.config['server_port'],
                "status": "online",
                "shared_files_count": 0
            }
            response = requests.post(
                f"{self.config['backend_url']}/register/node",
                json=node_info
            )
            if response.status_code == 200:
                logger.info("Nodo registrado correctamente")
            else:
                logger.error(f"Error al registrar nodo: {response.text}")
        except Exception as e:
            logger.error(f"Error al registrar nodo: {str(e)}")
    
    def _start_scanning(self):
        """Inicia el proceso de escaneo periódico"""
        def scan_loop():
            while self.running:
                try:
                    logger.info("Iniciando escaneo de archivos...")
                    files = self.scanner.scan()
                    logger.info(f"Se encontraron {len(files)} archivos")
                    
                    if files:
                        success = self.uploader.upload_metadata(files)
                        if success:
                            logger.info("Metadatos enviados correctamente")
                        else:
                            logger.error("Error al enviar metadatos")
                except Exception as e:
                    logger.error(f"Error durante el escaneo: {str(e)}")
                
                # Esperar hasta el próximo escaneo
                scan_interval = self.config.get('scan_interval_seconds', 300)  # 5 minutos por defecto
                logger.info(f"Próximo escaneo en {scan_interval} segundos")
                
                # Esperar en intervalos pequeños para permitir interrupciones
                for _ in range(scan_interval):
                    if not self.running:
                        break
                    time.sleep(1)
        
        # Iniciar en un thread separado
        self.scan_thread = threading.Thread(target=scan_loop)
        self.scan_thread.daemon = True
        self.scan_thread.start()
    
    def _start_heartbeats(self):
        """Inicia el envío periódico de heartbeats"""
        def heartbeat_loop():
            while self.running:
                try:
                    response = requests.post(
                        f"{self.config['backend_url']}/register/heartbeat/{self.config['node_id']}"
                    )
                    if response.status_code == 200:
                        logger.debug("Heartbeat enviado")
                    else:
                        logger.warning(f"Error al enviar heartbeat: {response.text}")
                except Exception as e:
                    logger.warning(f"Error al enviar heartbeat: {str(e)}")
                
                # Esperar hasta el próximo heartbeat
                heartbeat_interval = self.config.get('heartbeat_interval_seconds', 60)  # 1 minuto por defecto
                
                # Esperar en intervalos pequeños para permitir interrupciones
                for _ in range(heartbeat_interval):
                    if not self.running:
                        break
                    time.sleep(1)
        
        # Iniciar en un thread separado
        self.heartbeat_thread = threading.Thread(target=heartbeat_loop)
        self.heartbeat_thread.daemon = True
        self.heartbeat_thread.start()
    
    def _handle_exit(self, signum, frame):
        """Manejador de señales para salida limpia"""
        logger.info(f"Recibida señal {signum}, deteniendo agente...")
        self.stop()
        sys.exit(0)

if __name__ == "__main__":
    agent = Agent()
    agent.start()
