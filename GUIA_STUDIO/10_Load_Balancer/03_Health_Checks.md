# Health Checks

## En Nginx
```nginx
location /health {
    return 200 'OK';
    add_header Content-Type text/plain;
}
```
Endpoint simple para que Swarm verifique el contenedor.

## En Docker Swarm
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 10s
```
- `start_period`: ignora fallos durante arranque.
- Tras 3 fallos consecutivos, Swarm reinicia o reemplaza la tarea.

## Beneficios
- Backends no saludables se excluyen automáticamente del balanceo.
- Self-healing: Swarm recrea tareas fallidas.

## Health en backend
Cada slave expone `/api/v1/health` con conexiones a MongoDB, Redis y estado general; el load-balancer redirige a otros si falla.