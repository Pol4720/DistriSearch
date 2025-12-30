# 🎛️ DistriSearch Control Center

Centro de Control para monitoreo y pruebas del sistema distribuido DistriSearch.

## 📋 Características

- **Panel Principal**: Monitoreo en tiempo real del estado del cluster
- **Gestión de Nodos**: Control de contenedores Docker (iniciar, detener, pausar, kill)
- **Escenarios de Prueba**: Tests predefinidos para probar funcionalidades distribuidas
- **Métricas**: Visualización de métricas del sistema
- **Documentación**: Explicaciones de conceptos de sistemas distribuidos

## 🚀 Instalación y Ejecución

### Opción 1: Ejecución Local (Desarrollo)

#### Backend
```bash
cd backend
pip install -r requirements.txt
python main.py
```
El backend estará disponible en `http://localhost:8888`

#### Frontend (Streamlit)
```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py
```
El frontend estará disponible en `http://localhost:8501`

### Opción 2: Docker Compose

```bash
docker-compose up -d
```

- Frontend (Streamlit): `http://localhost:8501`
- Backend API: `http://localhost:8888`

## 📚 Escenarios de Prueba Disponibles

### 1. Failover de Líder
Prueba la elección de un nuevo líder cuando el actual falla.
- Concepto: **Raft Leader Election**

### 2. Recuperación de Nodo
Verifica cómo un nodo se recupera y sincroniza con el cluster.
- Concepto: **Log Replication, State Synchronization**

### 3. Partición de Red
Simula una partición de red y verifica el comportamiento.
- Concepto: **CAP Theorem, Partition Tolerance**

### 4. Balanceo de Carga
Prueba la distribución de búsquedas entre nodos.
- Concepto: **Load Balancing, Distributed Search**

### 5. Prueba de Replicación
Verifica que los datos se replican correctamente.
- Concepto: **Data Replication, Consistency**

### 6. Prueba de Estrés
Somete al sistema a carga elevada.
- Concepto: **Performance, Scalability**

## 🔧 Requisitos

- Python 3.11+
- Docker (para control de contenedores)
- DistriSearch corriendo en el puerto 8000

## 📖 API del Backend

### Cluster
- `GET /api/cluster/status` - Estado del cluster
- `GET /api/cluster/leader` - Info del líder
- `GET /api/cluster/replication` - Estado de replicación

### Nodes
- `GET /api/nodes/containers` - Lista contenedores
- `POST /api/nodes/stop/{name}` - Detener nodo
- `POST /api/nodes/start/{name}` - Iniciar nodo
- `POST /api/nodes/kill/{name}` - Matar nodo (SIGKILL)
- `POST /api/nodes/pause/{name}` - Pausar nodo (simula partición)
- `POST /api/nodes/unpause/{name}` - Reanudar nodo

### Tests
- `GET /api/tests/scenarios` - Lista escenarios
- `POST /api/tests/run/{id}` - Ejecutar escenario
- `GET /api/tests/results/{id}` - Resultados del test

### Metrics
- `GET /api/metrics/summary` - Resumen de métricas
- `GET /api/metrics/current` - Métricas actuales

## 🎨 Tecnologías

- **Backend**: FastAPI, Docker SDK, httpx
- **Frontend**: Streamlit, Plotly, Pandas
- **UI**: Diseño moderno con CSS personalizado y tema oscuro

## 📝 Notas

- El Control Center necesita acceso al socket de Docker para controlar contenedores
- En Linux, asegúrate de que el usuario tenga permisos para Docker
- Los escenarios de prueba pueden afectar el cluster en producción - usar con precaución
