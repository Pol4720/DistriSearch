# Verificación del Cluster

## Comandos básicos
```bash
docker node ls              # nodos del Swarm
docker service ls           # servicios desplegados
docker service ps <svc>     # tareas de un servicio
```

## Health checks
```bash
curl -k https://worker1:8443/health
curl http://manager1:8001/health
```
Deben devolver `OK` o JSON con estado.

## Logs
```bash
docker service logs distrisearch_slave --tail 100 -f
docker logs distrisearch-master
```

## Probar búsqueda distribuida
```bash
curl -k https://worker1:8443/api/v1/search?q=presupuesto
```

## Troubleshooting común
| Problema | Solución |
|----------|----------|
| Nodo no se une | Verificar puertos 2377, 7946, 4789 |
| DNS no resuelve | Revisar red overlay y CoreDNS |
| MongoDB no conecta | Comprobar nombre en red overlay |
| Master no responde | Ver logs Raft, verificar quorum |

## Escalar slaves
```bash
docker service scale distrisearch_slave=5
```