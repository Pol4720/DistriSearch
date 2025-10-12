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

- Búsqueda distribuida de archivos por nombre y contenido (Full‑Text Search)
- Descarga directa desde el nodo que contiene el archivo
- Tolerancia a fallos: si un nodo cae, los archivos siguen disponibles en otros
- Interfaz web intuitiva

### Nueva: Búsqueda por Contenido

Ahora el sistema indexa texto interno de múltiples formatos para permitir consultas que no solo coinciden con el nombre del archivo, sino también con palabras y frases presentes dentro de su contenido.

Formatos soportados (extracción best‑effort):
- TXT / archivos `text/*`
- PDF (PyPDF2)
- DOCX (python-docx)
- CSV / Excel (`.csv`, `.xlsx`) vía pandas / openpyxl
- Otros formatos se pueden añadir fácilmente (ej. Markdown, JSON) aprovechando la misma infraestructura.

Tecnologías empleadas:
- SQLite FTS5: se añadió una tabla virtual `file_contents` con tokenizador Porter (stemming en inglés) para realizar búsqueda full‑text eficiente y ranking BM25 ligero. Esto mantiene el despliegue sencillo (sin introducir aún ElasticSearch) y provee relevancia básica.
- Extracción incremental en el agente: cada agente extrae texto (limitado ~200KB por archivo para evitar saturación) y lo envía junto a los metadatos. Si no se puede extraer, aún se indexa el nombre para que el archivo siga siendo localizable.
- Estrategia híbrida nombre + contenido: el campo `name` también se indexa dentro de FTS para que el match exacto de nombre tenga un peso natural en el ranking (aplicamos un factor de ponderación en bm25 asignando pesos 1.0 para nombre y 0.5 para contenido).

Ventajas:
- Zero additional infra: sigue usando el mismo contenedor y base SQLite.
- Ranking básico por relevancia (BM25) sin complejidad extra.
- Fácil migración futura: la capa de servicio (`database.search_files`) encapsula la lógica; sustituirla por ElasticSearch / OpenSearch o motor vectorial será directo.

Limitaciones actuales y siguientes pasos sugeridos:
- No se hace extracción OCR de imágenes / PDFs escaneados (se podría integrar Tesseract o EasyOCR).
- Tokenización Porter está orientada a inglés; para soporte multi‑idioma se puede cambiar a tokenización simple y/o usar un motor externo.
- No se almacena snippet de contexto aún; podría añadirse generando un fragmento destacado (highlight) en el servicio de búsqueda.

Campos añadidos:
- `FileMeta.content` (opcional) se usa solo para indexación, no se expone completo en respuestas (se puede limpiar si se desea mostrar resumen en el futuro).

Si se activa una futura migración a ElasticSearch, bastará con mapear el pipeline de extracción existente a un índice con campos `name` (keyword + text) y `content` (text) y replicar los boosts.

## Próximas mejoras (Fase 2)

- Integración con Elasticsearch para búsquedas avanzadas
- Replicación de metadatos para mayor disponibilidad
- Autenticación y autorización
- Encriptación de comunicaciones
 - Eliminación de archivos y reindexación incremental
 - Integración de búsqueda semántica
   - OCR / extracción multi‑idioma y embeddings vectoriales para queries semánticas
