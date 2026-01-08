# Load Balancer en DistriSearch

Nginx actúa como punto de entrada único, distribuyendo tráfico entre los slaves y proporcionando SSL termination, rate limiting y health checks.

## Arquitectura
```
Cliente → Nginx (puerto 80/443) → slaves (8000/8443)
                              → master (8001) para API admin
```

## Características
| Función | Implementación |
|---------|----------------|
| Balanceo | Upstreams dinámicos con resolución DNS |
| SSL | Terminación TLS 1.2/1.3 en load-balancer |
| Rate limiting | 100 req/s API, 10 req/s uploads |
| Health checks | Verifica /health cada 30 s |
| Failover | proxy_next_upstream reintenta en otros backends |

## Despliegue Swarm
- Modo `global` en managers: un contenedor Nginx por manager para HA.
- Usa `ingress-network` para recibir tráfico externo y `distrisearch-network` para backends.

Detalles en los siguientes archivos.