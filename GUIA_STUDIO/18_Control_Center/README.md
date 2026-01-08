# Control Center de DistriSearch

El Control Center es una aplicación de administración y monitoreo construida con **Streamlit** (frontend) y **FastAPI** (backend).

## Características
- Panel principal con estado del cluster en tiempo real.
- Gestión de contenedores Docker (iniciar, detener, pausar, kill).
- Escenarios de prueba predefinidos (failover, recuperación, particiones).
- Visualización de métricas con Plotly.
- Documentación interactiva de conceptos distribuidos.

## Estructura
```
control-center/
├── backend/
│   ├── main.py          # FastAPI entry point
│   ├── routers/         # Endpoints (nodes, scenarios)
│   └── services/        # Lógica de negocio
├── frontend/
│   ├── 🏠_Panel_Principal.py  # Página principal Streamlit
│   └── pages/           # Páginas adicionales
├── docker-compose.yml
└── Dockerfile.*
```

## Ejecución
```bash
# Local
cd control-center/backend && python main.py
cd control-center/frontend && streamlit run 🏠_Panel_Principal.py

# Docker
docker compose up -d
```
- Frontend: http://localhost:8501
- Backend: http://localhost:8888

Detalles en los siguientes archivos.