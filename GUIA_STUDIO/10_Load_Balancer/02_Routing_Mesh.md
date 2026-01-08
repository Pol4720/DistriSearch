# Routing Mesh de Docker Swarm

## Concepto
Swarm publica puertos en todos los nodos; cualquier petición a `<nodo>:80` se enruta internamente al servicio correcto sin importar dónde corra.

## Configuración en compose
```yaml
ports:
  - target: 80
    published: 80
    protocol: tcp
    mode: ingress
```
- `mode: ingress`: habilita routing mesh (default).
- `mode: host`: expone solo en nodo local (sin mesh).

## Flujo
```
Cliente → 192.168.1.11:80 (worker1) → ingress VIP → load-balancer container (cualquier nodo)
```
Incluso si load-balancer corre en otro host, la petición llega.

## Combinación con Nginx
Nginx recibe vía routing mesh y luego balancea internamente hacia slaves usando upstreams dinámicos.