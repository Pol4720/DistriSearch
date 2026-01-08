# Arquitectura General de DistriSearch

## Visión Global del Sistema Distribuido

---

## Introducción

Esta sección explica la arquitectura general de DistriSearch, un sistema de búsqueda distribuida que implementa el patrón **Master-Slave con Load Balancer**. El sistema está diseñado para escalar horizontalmente, tolerar fallos y proporcionar búsqueda semántica sin depender de embeddings pre-entrenados.

---

## Contenido de esta Sección

| Archivo | Tema | Descripción |
|---------|------|-------------|
| [01_Vision_Sistema_Master_Slave.md](01_Vision_Sistema_Master_Slave.md) | **Patrón Master-Slave** | Roles del Master y Slaves, flujo de comunicación, arquitectura AP |
| [02_Componentes_Principales.md](02_Componentes_Principales.md) | **Componentes** | Load Balancer, nodos Slave, nodo Master, almacenamiento |
| [03_Estructura_Proyecto.md](03_Estructura_Proyecto.md) | **Estructura de Código** | Organización de carpetas, archivos clave, configuraciones |

---

## Diagrama de Arquitectura de Alto Nivel

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENTES                                       │
│                         (Navegadores / APIs)                                │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           LOAD BALANCER                                     │
│                         (Nginx + SSL/TLS)                                   │
│    • Round Robin / Least Connections    • Health Checks    • Rate Limiting  │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
            ┌─────────────────────┼─────────────────────┐
            │                     │                     │
            ▼                     ▼                     ▼
┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐
│     SLAVE 1       │   │     SLAVE 2       │   │     SLAVE N       │
│                   │   │                   │   │                   │
│ ┌───────────────┐ │   │ ┌───────────────┐ │   │ ┌───────────────┐ │
│ │   Frontend    │ │   │ │   Frontend    │ │   │ │   Frontend    │ │
│ │    (React)    │ │   │ │    (React)    │ │   │ │    (React)    │ │
│ ├───────────────┤ │   │ ├───────────────┤ │   │ ├───────────────┤ │
│ │   Backend     │ │   │ │   Backend     │ │   │ │   Backend     │ │
│ │  (FastAPI)    │ │   │ │  (FastAPI)    │ │   │ │  (FastAPI)    │ │
│ ├───────────────┤ │   │ ├───────────────┤ │   │ ├───────────────┤ │
│ │  MongoDB      │ │   │ │  MongoDB      │ │   │ │  MongoDB      │ │
│ │  Redis        │ │   │ │  Redis        │ │   │ │  Redis        │ │
│ │  SQLite       │ │   │ │  SQLite       │ │   │ │  SQLite       │ │
│ └───────────────┘ │   │ └───────────────┘ │   │ └───────────────┘ │
└─────────┬─────────┘   └─────────┬─────────┘   └─────────┬─────────┘
          │                       │                       │
          └───────────────────────┼───────────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │      MASTER NODE        │
                    │                         │
                    │  • VP-Tree Global       │
                    │  • Coordinación Raft    │
                    │  • Rebalanceo Activo    │
                    │  • Registro de Nodos    │
                    └─────────────────────────┘
```

---

## Principios de Diseño

### 1. Escalabilidad Horizontal

El sistema puede crecer añadiendo más nodos Slave sin modificar el código:

```
Inicial:  [Slave-1] [Slave-2]
             ↓         ↓
Escalado: [Slave-1] [Slave-2] [Slave-3] [Slave-4]
```

### 2. Tolerancia a Particiones (CAP: AP)

DistriSearch elige **Disponibilidad + Tolerancia a Particiones**:

- Cada nodo puede operar **independientemente** durante particiones de red
- **SQLite local** permite autenticación sin conexión al Master
- **Consistencia eventual** vía protocolo Gossip

### 3. Autonomía de Nodos

Cada Slave es una **unidad autónoma** que contiene:
- Su propio Frontend servido por Nginx
- Backend API completo (FastAPI)
- Base de datos MongoDB local
- Caché Redis local
- SQLite para usuarios (replicado con Raft)

### 4. Coordinación Centralizada

El Master coordina operaciones que requieren visión global:
- Asignación de documentos a nodos (VP-Tree)
- Rebalanceo cuando cambia la topología
- Elección de líder mediante Raft

---

## Flujo de Datos Principal

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Usuario │────►│ Load Balancer│────►│    Slave     │────►│   MongoDB    │
│          │     │   (Nginx)    │     │  (FastAPI)   │     │   (Local)    │
└──────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                                              │
                                              ▼
                                      ┌──────────────┐
                                      │    Master    │
                                      │ (Coordinar)  │
                                      └──────────────┘

1. Usuario hace request → Load Balancer
2. Load Balancer selecciona Slave (Round Robin)
3. Slave procesa la petición localmente
4. Para operaciones de escritura: consulta al Master
5. Master coordina particionamiento y replicación
```

---

## Tecnologías Principales

| Capa | Tecnología | Propósito |
|------|------------|-----------|
| **Presentación** | React + TypeScript | Interfaz de usuario |
| **API** | FastAPI (Python) | Backend REST |
| **Orquestación** | Docker Swarm | Despliegue distribuido |
| **Balanceo** | Nginx | Distribución de carga |
| **Búsqueda** | VP-Tree + MinHash | Particionamiento semántico |
| **Consenso** | Raft-Lite | Elección de líder |
| **Datos** | MongoDB + Redis + SQLite | Almacenamiento híbrido |

---

## Referencias del Código

Los archivos principales que definen la arquitectura:

```
DistriSearch/
├── backend/app/main.py           # Punto de entrada FastAPI
├── backend/app/config.py         # Configuración del sistema
├── backend/app/distributed/      # Módulos de distribución
│   ├── consensus/                # Implementación Raft
│   ├── coordination/             # Coordinación del cluster
│   └── communication/            # Comunicación entre nodos
├── docker/
│   ├── master/Dockerfile         # Imagen del Master
│   ├── slave/Dockerfile          # Imagen del Slave
│   └── load-balancer/nginx.conf  # Configuración Nginx
└── shared/models/                # Modelos compartidos
    ├── node.py                   # Modelo de nodo
    ├── cluster.py                # Modelo de cluster
    └── document.py               # Modelo de documento
```

---

## Preguntas Frecuentes de Estudio

1. **¿Por qué Master-Slave en lugar de P2P?**
   - Simplicidad en la coordinación
   - VP-Tree requiere visión global
   - Más fácil de debuggear y monitorizar

2. **¿Qué pasa si el Master falla?**
   - Los Slaves continúan operando (modo degradado)
   - Raft elige un nuevo líder automáticamente
   - Las búsquedas locales siguen funcionando

3. **¿Por qué MongoDB local en cada Slave?**
   - Elimina punto único de fallo
   - Permite operación durante particiones
   - Cada nodo es autónomo

---

> **Siguiente**: [01_Vision_Sistema_Master_Slave.md](01_Vision_Sistema_Master_Slave.md) para entender en detalle el patrón arquitectónico.