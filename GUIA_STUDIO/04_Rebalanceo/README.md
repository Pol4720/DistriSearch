# 04. Rebalanceo Activo

## Visión General

El **rebalanceo activo** es uno de los mecanismos más importantes en DistriSearch para mantener una distribución equilibrada de documentos cuando la topología del clúster cambia. Este módulo se activa automáticamente cuando:

- Un nuevo nodo se une al clúster
- Un nodo existente abandona el clúster
- Se detecta un desbalance de carga significativo

## ¿Por Qué Rebalancear?

```
┌─────────────────────────────────────────────────────────────────┐
│                    PROBLEMA SIN REBALANCEO                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Nodo_1: ████████████████████ 2000 docs (sobrecargado)         │
│   Nodo_2: ████████████████████ 2000 docs (sobrecargado)         │
│   Nodo_3: ██████████           1000 docs                         │
│   Nodo_4:                      0 docs (recién añadido)          │
│                                                                  │
│   → Latencia alta en Nodo_1 y Nodo_2                            │
│   → Nodo_4 desperdiciado                                        │
│   → Distribución desigual de consultas                          │
└─────────────────────────────────────────────────────────────────┘

                              ↓ REBALANCEO

┌─────────────────────────────────────────────────────────────────┐
│                    DESPUÉS DEL REBALANCEO                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Nodo_1: █████████████        1250 docs (equilibrado)          │
│   Nodo_2: █████████████        1250 docs (equilibrado)          │
│   Nodo_3: █████████████        1250 docs (equilibrado)          │
│   Nodo_4: █████████████        1250 docs (equilibrado)          │
│                                                                  │
│   → Carga distribuida uniformemente                             │
│   → Mejor tiempo de respuesta                                   │
│   → Utilización óptima de recursos                              │
└─────────────────────────────────────────────────────────────────┘
```

## Arquitectura del Rebalanceo

```
┌──────────────────────────────────────────────────────────────────┐
│                    SISTEMA DE REBALANCEO                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│   ┌─────────────────┐    ┌─────────────────┐                     │
│   │ LoadCalculator  │───▶│ ActiveRebalancer│                     │
│   │                 │    │                 │                     │
│   │ • Métricas      │    │ • Monitoreo     │                     │
│   │ • Varianza      │    │ • Decisiones    │                     │
│   │ • Umbrales      │    │ • Orquestación  │                     │
│   └─────────────────┘    └────────┬────────┘                     │
│                                   │                               │
│                                   ▼                               │
│                    ┌─────────────────────────┐                   │
│                    │   MigrationHandler      │                   │
│                    │                         │                   │
│                    │ • Batch transfers       │                   │
│                    │ • Rate limiting         │                   │
│                    │ • Retry logic           │                   │
│                    └─────────────────────────┘                   │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

## Componentes Principales

| Componente | Archivo | Responsabilidad |
|------------|---------|------------------|
| `ActiveRebalancer` | `active_rebalancer.py` | Orquesta todo el proceso de rebalanceo |
| `LoadCalculator` | `load_calculator.py` | Calcula métricas de carga y decide cuándo rebalancear |
| `MigrationHandler` | `migration_handler.py` | Ejecuta migraciones con batching y rate limiting |

## Fórmulas Clave

### Factor de Carga
$$load\_factor = \frac{document\_count}{capacity}$$

### Carga Combinada (ponderada)
$$combined\_load = 0.4 \cdot load\_factor + 0.2 \cdot storage\_factor + 0.2 \cdot cpu\_usage + 0.2 \cdot memory\_usage$$

### Umbral de Desbalance
$$needs\_rebalance = load\_std\_dev > 0.2 \lor imbalance\_ratio > 0.5$$

## Flujo de Rebalanceo

```
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│   ANALYZING   │────▶│   PLANNING    │────▶│   EXECUTING   │
│               │     │               │     │               │
│ Métricas      │     │ Decisiones    │     │ Migraciones   │
│ Cluster       │     │ de migración  │     │ en batches    │
│ summary       │     │               │     │               │
└───────────────┘     └───────────────┘     └───────────────┘
                                                    │
                                                    ▼
                                           ┌───────────────┐
                                           │   COMPLETED   │
                                           │               │
                                           │ + Cooldown    │
                                           │   (5 min)     │
                                           └───────────────┘
```

## Contenido de Esta Sección

1. **[Rebalanceo Activo](01_Rebalanceo_Activo.md)**: La clase `ActiveRebalancer` y su proceso completo
2. **[Power of Two Choices](02_Power_Two_Choices.md)**: Algoritmo de selección de nodo destino
3. **[Migración de Documentos](03_Migracion_Documentos.md)**: Proceso detallado de transferencia

---

**Navegación:**
- [← Anterior: Particionamiento](../03_Particionamiento/README.md)
- [→ Siguiente: Replicación](../05_Replicacion/README.md)
