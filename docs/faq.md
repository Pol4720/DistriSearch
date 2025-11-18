# Preguntas Frecuentes (FAQ)

Respuestas a las preguntas más comunes sobre DistriSearch.

---

## 🚀 General

### ¿Qué es DistriSearch?

DistriSearch es un sistema de búsqueda distribuida que permite indexar y buscar archivos en múltiples nodos sin necesidad de centralizar los datos. Cada nodo mantiene sus archivos localmente mientras participa en un índice global de búsqueda.

### ¿Para qué casos de uso es ideal DistriSearch?

- **Empresas distribuidas**: Oficinas en diferentes ubicaciones que necesitan buscar documentos sin centralizar
- **Instituciones académicas**: Múltiples departamentos con repositorios independientes
- **Equipos de desarrollo**: Búsqueda de código y documentación en microservicios
- **Healthcare**: Búsqueda de historiales médicos respetando la privacidad
- **Productoras**: Gestión de assets multimedia distribuidos

### ¿Cuál es la diferencia con Google Drive o Dropbox?

| Característica | DistriSearch | Google Drive/Dropbox |
|----------------|--------------|----------------------|
| **Almacenamiento** | Distribuido, datos en origen | Centralizado en la nube |
| **Privacidad** | Total, datos nunca salen | Datos en servidores terceros |
| **Coste** | Gratis, open source | Planes de pago por espacio |
| **Control** | Total sobre infraestructura | Limitado |
| **Búsqueda** | BM25 distribuida | Búsqueda centralizada |
| **Offline** | Cada nodo independiente | Requiere internet |

---

## 📦 Instalación y Configuración

### ¿Qué requisitos mínimos necesito?

**Por componente**:

- **Backend**: 2 GB RAM, 2 CPU cores, 10 GB disco
- **Frontend**: 1 GB RAM, 1 CPU core, 1 GB disco
- **Agente**: 512 MB RAM, 1 CPU core, espacio según datos

**Total recomendado**: 4 GB RAM, 4 CPU cores, SSD

### ¿Puedo instalarlo en Windows?

¡Sí! DistriSearch es multiplataforma:

- ✅ Windows 10/11
- ✅ Linux (Ubuntu, Debian, CentOS, etc.)
- ✅ macOS

La instalación con Docker es la misma en todos los sistemas.

### ¿Necesito Docker obligatoriamente?

No, Docker es opcional. Puedes instalar localmente con Python 3.8+:

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app

# Frontend
cd frontend
pip install -r requirements.txt
streamlit run app.py

# Agente
cd agent
pip install -r requirements.txt
python agent.py
```

### ¿Cómo cambio el puerto por defecto?

**Backend** (puerto 8000):
```bash
uvicorn main:app --port 8080
```

**Frontend** (puerto 8501):
```bash
streamlit run app.py --server.port 8502
```

**Agente** (puerto 5001):
```yaml
# config.yaml
agent:
  port: 5002
```

---

## 🌐 Nodos y Arquitectura

### ¿Cuántos nodos puedo tener?

No hay límite teórico. En pruebas hemos validado hasta **100 nodos** sin problemas. El límite práctico depende de tu infraestructura de red y el hardware del backend.

### ¿Qué pasa si un nodo está offline?

- ✅ La búsqueda continúa en los nodos activos
- ✅ Los resultados del nodo offline no aparecen
- ✅ El nodo se reintegra automáticamente al volver online
- ✅ Si usas **modo central**, los archivos replicados siguen disponibles

### ¿Los nodos deben estar en la misma red?

No necesariamente:

- **Red local**: Configuración más simple, menor latencia
- **Internet**: Posible con IPs públicas o VPN
- **VPN**: Recomendado para seguridad en internet
- **Docker Swarm**: Para múltiples hosts en producción

### ¿Cómo funciona el heartbeat?

Cada agente envía un "heartbeat" al backend cada 30 segundos (configurable):

```yaml
backend:
  heartbeat_interval: 30  # segundos
```

Si el backend no recibe heartbeat en 60 segundos, marca el nodo como `offline`.

---

## 🔍 Búsqueda

### ¿Cómo funciona el algoritmo BM25?

BM25 (Best Matching 25) es un algoritmo de ranking que considera:

1. **Frecuencia del término**: Cuántas veces aparece la palabra
2. **Longitud del documento**: Normaliza por tamaño
3. **IDF (Inverse Document Frequency)**: Penaliza palabras muy comunes

**Fórmula simplificada**:

$$
\text{score} = IDF(q) \cdot \frac{f(q,D) \cdot (k_1 + 1)}{f(q,D) + k_1 \cdot (1 - b + b \cdot \frac{|D|}{avgdl})}
$$

Donde:
- $k_1 = 1.5$ (saturación de frecuencia)
- $b = 0.75$ (normalización de longitud)

### ¿Puedo buscar dentro del contenido de los archivos?

Sí, habilitando **full-text indexing**:

```yaml
# agent/config.yaml
metadata:
  full_text_indexing: true
  max_text_size: 1048576  # 1 MB
```

⚠️ **Advertencia**: Aumenta significativamente el tiempo de indexación y uso de recursos.

### ¿La búsqueda es case-sensitive?

No, la búsqueda es **case-insensitive** por defecto:

- `"Proyecto"` = `"proyecto"` = `"PROYECTO"`

### ¿Soporta búsquedas con operadores?

Actualmente no soporta operadores booleanos (AND, OR, NOT), pero está en el roadmap para v2.0.

**Workaround actual**: Usar múltiples búsquedas y filtrar en el frontend.

### ¿Qué tan rápida es la búsqueda?

Depende del número de nodos y archivos:

| Escenario | Nodos | Archivos | Tiempo |
|-----------|-------|----------|--------|
| Pequeño | 1-3 | < 10K | 50-200 ms |
| Mediano | 5-10 | 10K-50K | 200-500 ms |
| Grande | 10-50 | 50K-200K | 500-2000 ms |
| Muy Grande | 50-100 | 200K+ | 2-5 seg |

---

## 📁 Archivos e Indexación

### ¿Qué tipos de archivos puedo indexar?

Por defecto:

```yaml
- .pdf, .doc, .docx  # Documentos
- .txt, .md          # Texto
- .xlsx, .xls, .csv  # Hojas de cálculo
- .pptx, .ppt        # Presentaciones
```

Puedes agregar cualquier extensión:

```yaml
scan:
  file_types:
    - ".py"
    - ".js"
    - ".mp4"
    - ".jpg"
```

### ¿Con qué frecuencia se escanean los archivos?

Configurable en cada agente:

```yaml
scan:
  interval: 300  # 5 minutos
```

Recomendaciones:

- **Desarrollo**: 60-120 segundos
- **Producción estable**: 300-600 segundos
- **Archivos estáticos**: 1800-3600 segundos

### ¿Se detectan archivos duplicados?

Sí, usando **checksum SHA256**:

```yaml
scan:
  calculate_checksum: true
  checksum_algorithm: "sha256"
```

El backend identifica duplicados por hash y muestra una advertencia en el frontend.

### ¿Qué pasa si elimino un archivo?

El agente detecta la eliminación en el siguiente escaneo y notifica al backend para actualizar el índice.

### ¿Puedo indexar archivos muy grandes?

Sí, pero con límites configurables:

```yaml
scan:
  max_file_size: 524288000  # 500 MB
```

⚠️ **Nota**: Archivos muy grandes aumentan el tiempo de indexación y checksum.

---

## 💾 Base de Datos y Almacenamiento

### ¿Dónde se almacenan los datos?

**Backend**: Base de datos SQLite en `backend/distrisearch.db`

**Agentes**: Caché local opcional para metadatos

**Archivos**: Siempre en su ubicación original

### ¿Puedo usar PostgreSQL o MySQL?

Sí, cambiando la configuración:

```python
# backend/config.py
DATABASE_URL = "postgresql://user:pass@localhost/distrisearch"
# o
DATABASE_URL = "mysql://user:pass@localhost/distrisearch"
```

Requiere instalar el driver correspondiente:

```bash
pip install psycopg2-binary  # PostgreSQL
pip install pymysql          # MySQL
```

### ¿Qué tan grande puede ser la base de datos?

SQLite soporta hasta **281 TB**, más que suficiente para millones de archivos.

**Referencia**: 1 millón de archivos ≈ 500 MB de base de datos

---

## 🔐 Seguridad y Privacidad

### ¿Los archivos son privados?

**Sí, completamente**:

- ✅ Los archivos **nunca** salen de su ubicación original
- ✅ Solo se indexan metadatos (nombre, tamaño, tipo)
- ✅ El contenido no se copia al backend
- ✅ La descarga es directa desde el nodo

### ¿Cómo habilito autenticación?

```bash
# backend/.env
API_KEY_ENABLED=true
API_KEY=your-super-secret-key
```

Todas las peticiones requieren el header:

```http
X-API-Key: your-super-secret-key
```

### ¿Soporta HTTPS/SSL?

Sí, configurando certificados:

```python
# main.py
uvicorn.run(
    "main:app",
    ssl_keyfile="./key.pem",
    ssl_certfile="./cert.pem"
)
```

### ¿Es compatible con HIPAA/GDPR?

DistriSearch proporciona las herramientas técnicas para cumplir con estas regulaciones:

- ✅ Encriptación end-to-end (opcional)
- ✅ Auditoría de búsquedas
- ✅ Control de acceso por roles
- ✅ Datos descentralizados

⚠️ **Importante**: La configuración específica para compliance es responsabilidad del implementador.

---

## 🐳 Docker y Despliegue

### ¿Cómo actualizo los contenedores?

```bash
# Detener servicios
docker-compose down

# Actualizar imágenes
docker-compose pull

# Reiniciar
docker-compose up -d
```

### ¿Puedo usar Kubernetes?

Sí, ver [Guía de Kubernetes](deployment/kubernetes.md).

### ¿Soporta Docker Swarm?

Sí, ver [Guía de Docker Swarm](deployment/docker-swarm.md).

### ¿Cómo escalo el backend?

**Docker Swarm**:
```bash
docker service scale distrisearch_backend=5
```

**Kubernetes**:
```bash
kubectl scale deployment backend --replicas=5
```

---

## 🐛 Problemas Comunes

### Error: "Port already in use"

```bash
# Linux/Mac
lsof -ti:8000 | xargs kill -9

# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### Error: "Module not found"

```bash
# Reinstalar dependencias
pip install --force-reinstall -r requirements.txt
```

### Frontend no se conecta al backend

1. Verificar que el backend está corriendo:
   ```bash
   curl http://localhost:8000/health
   ```

2. Verificar URL en el frontend:
   ```python
   # frontend/config.py
   BACKEND_URL = "http://localhost:8000"  # o IP correcta
   ```

### Agente no se registra

1. Verificar conectividad:
   ```bash
   ping <backend_ip>
   curl http://<backend_ip>:8000/health
   ```

2. Verificar configuración:
   ```yaml
   backend:
     url: "http://192.168.1.100:8000"  # IP correcta
   ```

### No aparecen archivos en búsqueda

1. Verificar que el agente escaneó:
   ```bash
   curl http://localhost:5001/files
   ```

2. Forzar escaneo:
   ```bash
   curl -X POST http://localhost:5001/scan
   ```

3. Verificar permisos de carpeta:
   ```bash
   ls -la /ruta/shared_folder
   ```

---

## 🚀 Rendimiento

### ¿Cómo optimizo la velocidad de búsqueda?

1. **Usar SSD**: 3-5x más rápido que HDD
2. **Más RAM**: Permite más caché
3. **Mejor CPU**: Para procesamiento paralelo
4. **Red rápida**: 100 Mbps+ recomendado
5. **Limitar tipos de archivo**: Solo indexar lo necesario

### ¿La búsqueda es paralela?

Sí, el backend busca en todos los nodos **simultáneamente** usando `asyncio`.

### ¿Puedo ajustar el timeout?

```python
# backend/config.py
SEARCH_TIMEOUT = 30  # segundos
```

Aumentar si los nodos son lentos o la red es lenta.

---

## 🔮 Roadmap y Futuro

### ¿Qué nuevas funcionalidades están planeadas?

Ver [Roadmap completo](caracteristicas.md#roadmap), highlights:

- 🔍 Búsqueda semántica con embeddings
- 🤖 Interfaz de chat con LLM
- 🔐 Autenticación OAuth2/OIDC
- 📊 Dashboard analytics avanzado
- 🌐 Replicación automática inteligente
- 📱 App móvil

### ¿Puedo contribuir?

¡Por supuesto! Ver [Guía de Contribución](development/contribucion.md).

---

## 📞 Soporte

### ¿Dónde reporto bugs?

[GitHub Issues](https://github.com/Pol4720/DS-Project/issues)

### ¿Hay comunidad o foro?

Actualmente en GitHub Discussions. Próximamente Discord.

### ¿Ofrecen soporte empresarial?

Para soporte empresarial, contactar: [pol4720@example.com](mailto:pol4720@example.com)

---

[:octicons-arrow-left-24: Volver](index.md){ .md-button }
[:octicons-mark-github-24: GitHub Issues](https://github.com/Pol4720/DS-Project/issues){ .md-button .md-button--primary }
