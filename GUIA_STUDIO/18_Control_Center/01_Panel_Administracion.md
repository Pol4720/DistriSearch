# Panel de Administración

## Tecnología: Streamlit
Streamlit permite crear dashboards interactivos en Python puro:
```python
import streamlit as st
st.title("DistriSearch Control Center")
if st.button("Rebalancear"):
    trigger_rebalance()
```

## Componentes principales
| Componente | Función |
|------------|--------|
| Sidebar | Navegación entre páginas |
| Cards de nodos | Estado, CPU, memoria por nodo |
| Tabla de particiones | Asignaciones VP-Tree |
| Botón de acciones | Iniciar, detener, pausar contenedores |

## Escenarios de prueba
1. **Failover de líder**: detiene master y verifica nueva elección.
2. **Recuperación de nodo**: reinicia slave y valida sincronización.
3. **Partición de red**: simula split-brain y observa comportamiento.
4. **Rebalanceo**: agrega nodo y dispara redistribución.

## Backend
FastAPI expone endpoints consumidos por Streamlit:
- `GET /nodes`: lista contenedores Docker.
- `POST /nodes/{id}/stop`: detiene contenedor.
- `POST /scenarios/{name}`: ejecuta escenario de prueba.

El backend se comunica con Docker API vía socket.