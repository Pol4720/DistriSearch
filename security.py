"""
Seguridad básica: TLS + autenticación JWT.
"""
import ssl
import jwt
import time
from typing import Optional, Dict
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class SecurityManager:
    """Gestiona TLS y autenticación JWT."""
    
    # Secret key para JWT (en producción: variable de entorno)
    JWT_SECRET = "CAMBIAR_EN_PRODUCCION"
    JWT_ALGORITHM = "HS256"
    TOKEN_EXPIRY = 3600  # 1 hora
    
    def __init__(self, enable_tls: bool = True, cert_dir: Optional[Path] = None):
        self.enable_tls = enable_tls
        self.cert_dir = cert_dir or Path("certs")
        self.ssl_context: Optional[ssl.SSLContext] = None
        
        if enable_tls:
            self._setup_tls()
    
    def _setup_tls(self):
        """Configura SSL context para TLS."""
        try:
            self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            
            cert_file = self.cert_dir / "server.crt"
            key_file = self.cert_dir / "server.key"
            
            if cert_file.exists() and key_file.exists():
                self.ssl_context.load_cert_chain(cert_file, key_file)
                logger.info("TLS habilitado con certificados")
            else:
                logger.warning(
                    f"Certificados no encontrados en {self.cert_dir}. "
                    "Genera con: openssl req -x509 -newkey rsa:4096 -nodes "
                    "-keyout server.key -out server.crt -days 365"
                )
                self.enable_tls = False
                self.ssl_context = None
                
        except Exception as e:
            logger.error(f"Error configurando TLS: {e}")
            self.enable_tls = False
            self.ssl_context = None
    
    def generate_token(self, node_id: int, metadata: Optional[Dict] = None) -> str:
        """Genera JWT para autenticación de nodo."""
        payload = {
            "node_id": node_id,
            "iat": time.time(),
            "exp": time.time() + self.TOKEN_EXPIRY
        }
        
        if metadata:
            payload.update(metadata)
        
        token = jwt.encode(payload, self.JWT_SECRET, algorithm=self.JWT_ALGORITHM)
        return token
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """Verifica y decodifica JWT."""
        try:
            payload = jwt.decode(token, self.JWT_SECRET, algorithms=[self.JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token expirado")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Token inválido: {e}")
            return None
    
    def get_ssl_context(self) -> Optional[ssl.SSLContext]:
        """Retorna SSL context para aiohttp."""
        return self.ssl_context if self.enable_tls else None