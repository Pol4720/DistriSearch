# MongoDB Local por Nodo

## Arquitectura
Cada slave tiene su propia instancia MongoDB corriendo como contenedor o sidecar.

```
worker1: MongoDB (mongodb-data-worker1) ← slave-worker1
worker2: MongoDB (mongodb-data-worker2) ← slave-worker2
...
```

## Conexión
```bash
MONGODB_URI=mongodb://mongodb-local:27017/distrisearch
```
El nombre `mongodb-local` resuelve al contenedor local vía red overlay.

## Qué se almacena
- Documentos (contenido original, metadatos).
- Vectores TF-IDF, MinHash, LDA.
- Índices para búsqueda local.

## Beneficios
- Sin SPOF: la caída de un MongoDB afecta solo ese nodo.
- Escalabilidad horizontal: agregar nodos = agregar almacenamiento.
- Partición de red: el nodo sigue sirviendo sus datos locales.

## Replica set (opcional)
En despliegues con más disponibilidad, se puede configurar un replica set por zona con init-replica.js.