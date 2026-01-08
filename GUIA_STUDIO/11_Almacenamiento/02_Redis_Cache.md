# Redis Cache

## Propósito
Acelerar lecturas frecuentes: resultados de búsqueda, embeddings precalculados, sesión de usuario.

## Configuración
```yaml
redis:
  image: redis:7-alpine
  command: ["redis-server", "--appendonly", "yes"]
  volumes:
    - redis-data:/data
```
- `appendonly yes`: persistencia AOF para recuperar datos tras reinicio.

## Conexión
```bash
REDIS_URL=redis://redis:6379
```

## Estrategia de caché
- TTL cortos (30–60 s) para resultados de búsqueda.
- Invalidación explícita al subir/eliminar documentos.
- Cache aside: si no está en Redis, consultar MongoDB y guardar.

## Despliegue Swarm
- Modo `replicated: 1` en manager (singleton).
- Para HA se puede usar Redis Sentinel o Redis Cluster, pero agrega complejidad.