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
