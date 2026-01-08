# Monitoreo del Cluster

## Métricas visualizadas
| Métrica | Fuente | Visualización |
|---------|--------|---------------|
| Estado de nodos | Docker API | Iconos verde/rojo |
| Líder Raft | Endpoint /cluster | Badge destacado |
| Particiones | Master API | Tabla con node_id |
| Documentos | MongoDB | Contador por nodo |
| Latencia | Health checks | Gauge Plotly |

## Actualización en tiempo real
Streamlit `st.fragment` permite refrescar secciones sin recargar toda la página:
```python
@st.fragment(run_every=5)
def cluster_status():
    data = fetch_cluster_status()
    render_cards(data)
```

## Alertas
- Nodo caído: tarjeta roja con tiempo desde último heartbeat.
- Sin líder: banner de advertencia.
- Réplicas insuficientes: indicador en partición afectada.

## Gráficos Plotly
- Gauge de salud general.
- Timeline de eventos (failover, rebalanceo).
- Heatmap de carga por nodo.

## Integración
El Control Center consulta tanto el backend propio (8888) como los endpoints del cluster DistriSearch (8001, 8000) para obtener datos en vivo.