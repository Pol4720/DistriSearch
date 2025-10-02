<p align="center">
  <img src="DistriSearch/assets/logo.png" alt="DistriSearch Logo" width="200"/>
</p>

# DistriSearch - Sistema de Búsqueda Distribuida

DistriSearch es un sistema de búsqueda y compartición de archivos distribuido. Permite a múltiples nodos compartir archivos, mientras un sistema central indexa los metadatos y facilita las búsquedas y descargas.

## Arquitectura

El sistema consta de tres componentes principales:

1. **Backend** (FastAPI): API centralizada que gestiona el índice de metadatos, registra nodos y responde a consultas.
2. **Agentes**: Clientes que se ejecutan en cada nodo, escanean carpetas compartidas y exponen un servidor para compartir archivos.
3. **Frontend** (Streamlit): Interfaz de usuario para realizar búsquedas y descargas.

### Modo Centralizado (Nuevo)
Para la primera entrega o demostraciones rápidas, el sistema puede funcionar sin agentes distribuidos:
1. El backend escanea una única carpeta local (`CENTRAL_SHARED_FOLDER` o `./central_shared`).
2. Crea un nodo sintético `central` y registra todos los archivos.
3. Las búsquedas funcionan igual y las descargas usan `GET /central/file/{file_id}`.
4. El frontend permite alternar entre modos en la barra lateral.

Endpoints clave:
| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/central/scan` | Escanea e indexa carpeta central |
| GET | `/central/mode` | Estado de modos centralizado/distribuido |
| GET | `/central/file/{file_id}` | Descarga directa archivo central |

## Instalación y uso

### Desarrollo local

1. Clona este repositorio
2. Crea carpetas compartidas para los agentes:
   ```
   mkdir -p deploy/shared_folders/agent1
   mkdir -p deploy/shared_folders/agent2
   ```
3. Coloca archivos en las carpetas compartidas
4. Ejecuta el sistema con Docker Compose:
   ```
   cd deploy
   docker-compose up -d
   ```
5. Accede al frontend en `http://localhost:8501`

### Despliegue distribuido (Docker Swarm)

1. Inicializa un cluster Swarm:
   ```
   docker swarm init
   ```
2. Despliega el stack:
   ```
   docker stack deploy -c deploy/docker-stack.yml distrisearch
   ```

## Características

- Búsqueda distribuida de archivos por nombre
- Descarga directa desde el nodo que contiene el archivo
- Tolerancia a fallos: si un nodo cae, los archivos siguen disponibles en otros
- Interfaz web intuitiva

## Próximas mejoras (Fase 2)

- Integración con Elasticsearch para búsquedas avanzadas
- Replicación de metadatos para mayor disponibilidad
- Autenticación y autorización
- Encriptación de comunicaciones
 - Eliminación de archivos y reindexación incremental
 - Integración de búsqueda semántica
