# Introducción a DistriSearch

## Sistema de Búsqueda Distribuida con Vectorización Semántica

---

## 1. ¿Qué es DistriSearch?

**DistriSearch** es un sistema de búsqueda distribuida diseñado para almacenar, indexar y buscar documentos de manera eficiente a través de múltiples nodos. A diferencia de los motores de búsqueda tradicionales, DistriSearch utiliza **vectorización semántica adaptativa** para encontrar documentos similares basándose en su significado, no solo en coincidencias exactas de palabras.

### Características Principales

| Característica | Descripción |
|----------------|-------------|
| **Búsqueda Semántica** | Encuentra documentos por similitud de significado usando TF-IDF + MinHash |
| **Arquitectura Distribuida** | Escala horizontalmente añadiendo más nodos al cluster |
| **Alta Disponibilidad** | Continúa operando incluso durante fallos de nodos o particiones de red |
| **Rebalanceo Automático** | Redistribuye documentos inteligentemente cuando cambia la topología |
| **Sin Embeddings Pre-entrenados** | Vectorización adaptativa que se ajusta al corpus local |

### Diagrama de Alto Nivel

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENTES                                │
│                    (Navegadores / APIs)                         │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LOAD BALANCER                              │
│                   (Nginx - SSL/Health)                          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│   SLAVE 1     │   │   SLAVE 2     │   │   SLAVE N     │
│ ┌───────────┐ │   │ ┌───────────┐ │   │ ┌───────────┐ │
│ │ Frontend  │ │   │ │ Frontend  │ │   │ │ Frontend  │ │
│ │  (React)  │ │   │ │  (React)  │ │   │ │  (React)  │ │
│ ├───────────┤ │   │ ├───────────┤ │   │ ├───────────┤ │
│ │ Backend   │ │   │ │ Backend   │ │   │ │ Backend   │ │
│ │ (FastAPI) │ │   │ │ (FastAPI) │ │   │ │ (FastAPI) │ │
│ ├───────────┤ │   │ ├───────────┤ │   │ ├───────────┤ │
│ │ MongoDB   │ │   │ │ MongoDB   │ │   │ │ MongoDB   │ │
│ │ Redis     │ │   │ │ Redis     │ │   │ │ Redis     │ │
│ │ SQLite    │ │   │ │ SQLite    │ │   │ │ SQLite    │ │
│ └───────────┘ │   │ └───────────┘ │   │ └───────────┘ │
└───────┬───────┘   └───────┬───────┘   └───────┬───────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                            ▼
              ┌─────────────────────────┐
              │      MASTER NODE        │
              │  • VP-Tree Global       │
              │  • Coordinación Raft    │
              │  • Rebalanceo Activo    │
              └─────────────────────────┘
```

---

## 2. Problema que Resuelve

### 2.1 ¿Por qué Búsqueda Distribuida?

Los sistemas de búsqueda centralizados enfrentan limitaciones críticas:

| Problema | Impacto | Solución DistriSearch |
|----------|---------|----------------------|
| **Escalabilidad limitada** | Un servidor no puede indexar millones de documentos | Particionamiento horizontal con VP-Tree |
| **Punto único de fallo** | Si cae el servidor, todo el sistema falla | Replicación con afinidad semántica |
| **Latencia en búsquedas** | Búsquedas lentas con corpus grandes | Índices locales + búsqueda paralela |
| **Búsqueda por keywords** | No encuentra documentos semánticamente similares | Vectorización TF-IDF + MinHash |

### 2.2 ¿Por qué Sin Embeddings Pre-entrenados?

Los embeddings pre-entrenados (como Word2Vec, BERT) tienen limitaciones:

- **Dimensión fija**: Pierden información en documentos extensos
- **Dependencia externa**: Requieren modelos grandes (GB)
- **Dominio genérico**: No se adaptan al vocabulario específico del corpus

**Solución DistriSearch**: Vectores TF-IDF jerárquicos entrenados localmente en el corpus del cluster, combinados con MinHash para similaridad eficiente.

### 2.3 Teorema CAP y DistriSearch

DistriSearch implementa un sistema **AP (Available & Partition-tolerant)**:

```
                    CONSISTENCIA (C)
                         /\
                        /  \
                       /    \
                      /  CA  \
                     /________\
                    /\        /\
                   /  \  CP  /  \
                  / AP \    /    \
                 /______\  /______\
        DISPONIBILIDAD (A)    TOLERANCIA A 
                              PARTICIONES (P)
                              
        DistriSearch elige: AP
        ─────────────────────
        ✅ Disponibilidad: Nodos operan independientemente
        ✅ Particiones: Soporta fallos de red
        ⚠️ Consistencia: Eventual (Gossip protocol)
```

---

## 3. Stack Tecnológico

### 3.1 Backend (Python)

| Tecnología | Propósito |
|------------|-----------|
| **FastAPI** | Framework web asíncrono de alto rendimiento |
| **Motor de Vectorización** | TF-IDF jerárquico + MinHash + LDA |
| **VP-Tree** | Particionamiento del espacio vectorial |
| **Raft-Lite** | Consenso para elección de líder |
| **Gossip Protocol** | Sincronización eventual del registry |

### 3.2 Frontend (TypeScript)

| Tecnología | Propósito |
|------------|-----------|
| **React** | Librería de UI con componentes |
| **TypeScript** | Tipado estático para JavaScript |
| **Vite** | Bundler rápido para desarrollo |
| **Tailwind CSS** | Framework de estilos utility-first |

### 3.3 Infraestructura

| Tecnología | Propósito |
|------------|-----------|
| **Docker Swarm** | Orquestación de contenedores distribuidos |
| **Nginx** | Load balancer y terminación SSL |
| **CoreDNS** | Backup DNS para service discovery |
| **MongoDB** | Almacenamiento de documentos (local por nodo) |
| **Redis** | Caché local para búsquedas frecuentes |
| **SQLite + Raft** | Usuarios y metadatos (replicado) |

### 3.4 Diagrama de Tecnologías por Capa

```
┌─────────────────────────────────────────────────────────────┐
│                    CAPA DE PRESENTACIÓN                     │
│  React + TypeScript + Vite + Tailwind                       │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      CAPA DE API                            │
│  FastAPI + Pydantic + JWT Auth                              │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                   CAPA DE NEGOCIO                           │
│  VP-Tree Partitioner + MinHash + TF-IDF + LDA               │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                 CAPA DE COORDINACIÓN                        │
│  Raft Consensus + Gossip Protocol + Rebalancer              │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                 CAPA DE ALMACENAMIENTO                      │
│  MongoDB (docs) + Redis (cache) + SQLite (users)            │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                 CAPA DE INFRAESTRUCTURA                     │
│  Docker Swarm + Nginx LB + CoreDNS + Overlay Network        │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Audiencia Objetivo

Esta guía de estudio está diseñada para **estudiantes de la asignatura de Sistemas Distribuidos** que necesitan:

1. **Comprender la arquitectura**: Entender por qué se tomaron las decisiones de diseño
2. **Dominar los conceptos**: Raft, Gossip, VP-Tree, CAP theorem, etc.
3. **Analizar la implementación**: Código real en Python y TypeScript
4. **Preparar la exposición**: Explicar cada componente con claridad

### Conocimientos Previos Recomendados

- Programación en Python y JavaScript/TypeScript
- Conceptos básicos de Docker y contenedores
- Fundamentos de redes (TCP/IP, DNS, HTTP)
- Bases de datos relacionales y NoSQL

---

## 5. Estructura de la Guía de Estudio

Esta guía está organizada en **18 secciones** que cubren todos los aspectos del sistema:

### Arquitectura y Diseño

| Sección | Contenido |
|---------|-----------|
| **01_Arquitectura_General** | Visión Master-Slave, componentes principales, estructura del proyecto |
| **02_Vectorizacion_Busqueda** | TF-IDF jerárquico, MinHash, LSH, vectores adaptativos |
| **03_Particionamiento** | VP-Tree distribuido, algoritmo de asignación, vantage points |

### Distribución y Coordinación

| Sección | Contenido |
|---------|-----------|
| **04_Rebalanceo** | Rebalanceo activo, Power of Two Choices, migración de documentos |
| **05_Replicacion** | Afinidad semántica, grafo de similaridad, factor de replicación |
| **06_Tolerancia_Fallos** | Detección de fallos, re-replicación, recuperación de nodos |
| **07_Consenso_Raft** | Elección de líder, replicación de log, SQLite con Raft |

### Infraestructura

| Sección | Contenido |
|---------|-----------|
| **08_Docker_Swarm** | Conceptos de Swarm, overlay networks, servicios y réplicas |
| **09_DNS_Descubrimiento** | DNS interno de Docker, CoreDNS backup, service discovery |
| **10_Load_Balancer** | Configuración Nginx, routing mesh, health checks, SSL |

### Almacenamiento y Consistencia

| Sección | Contenido |
|---------|-----------|
| **11_Almacenamiento** | MongoDB local, Redis cache, SQLite usuarios, UserDocumentRegistry |
| **12_Gossip_Protocol** | Consistencia eventual, sincronización del registry |
| **13_CAP_Theorem** | Availability + Partition Tolerance, trade-offs de DistriSearch |

### Implementación

| Sección | Contenido |
|---------|-----------|
| **14_Despliegue** | Preparación de imágenes, inicialización Swarm, verificación |
| **15_API_Backend** | FastAPI estructura, endpoints principales, autenticación |
| **16_Frontend** | React + TypeScript, componentes, servicios de API |
| **17_Testing** | Tests unitarios, integración, tests distribuidos |
| **18_Control_Center** | Panel de administración, monitoreo del cluster |

---

## 6. Cómo Usar Esta Guía

### Para Estudio Individual

1. **Lee secuencialmente** las secciones 01-07 para entender la teoría
2. **Explora el código** referenciado en cada sección
3. **Ejecuta el sistema** localmente con `docker-compose.local.yml`
4. **Experimenta** modificando parámetros y observando el comportamiento

### Para Preparar la Exposición

1. **Identifica tu tema** asignado y estudia la sección correspondiente
2. **Prepara diagramas** basándote en los ASCII arts proporcionados
3. **Practica explicando** los conceptos a un compañero
4. **Prepara preguntas** que el tribunal podría hacer

### Comandos Útiles para Empezar

```bash
# Clonar el proyecto
git clone https://github.com/Pol4720/DistriSearch.git
cd DistriSearch

# Ejecutar en modo local (desarrollo)
docker-compose -f docker/docker-compose.local.yml up -d

# Ver logs del sistema
docker-compose -f docker/docker-compose.local.yml logs -f

# Ejecutar tests
pytest tests/ -v
```

---

## 7. Recursos Adicionales

### Documentación del Proyecto

- [docs/Arquitectura de Software.md](../DistriSearch/docs/Arquitectura%20de%20Software.md) - Diseño general
- [docs/ARQUITECTURA_DISTRIBUIDA.md](../DistriSearch/docs/ARQUITECTURA_DISTRIBUIDA.md) - Docker Swarm y DNS
- [docs/Soluciones de ubicacion y balanceo.md](../DistriSearch/docs/Soluciones%20de%20ubicacion%20y%20balanceo.md) - Vectorización y particionamiento
- [deploy/manual-swarm/GUIA_DESPLIEGUE.md](../DistriSearch/deploy/manual-swarm/GUIA_DESPLIEGUE.md) - Despliegue paso a paso

### Conceptos Teóricos (Referencias Externas)

- **Raft Consensus**: [The Raft Paper](https://raft.github.io/raft.pdf)
- **VP-Trees**: [Vantage-Point Trees](https://en.wikipedia.org/wiki/Vantage-point_tree)
- **CAP Theorem**: [Brewer's Conjecture](https://en.wikipedia.org/wiki/CAP_theorem)
- **Gossip Protocol**: [Epidemic Algorithms](https://en.wikipedia.org/wiki/Gossip_protocol)
- **MinHash/LSH**: [Locality-Sensitive Hashing](https://en.wikipedia.org/wiki/MinHash)

---

> **Nota**: Esta guía está diseñada para complementar el código fuente. Se recomienda tener el proyecto abierto en VS Code mientras se estudia cada sección.