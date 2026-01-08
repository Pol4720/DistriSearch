# Inicialización de Docker Swarm

## Script automatizado

```bash
./02-init-swarm.sh [IP_DEL_MANAGER]
```

El script realiza:
1. Detecta IP automáticamente si no se especifica
2. Verifica Docker funcionando
3. **Configura firewall automáticamente** (UFW/iptables)
4. Inicializa Swarm
5. Crea red overlay `distrisearch-network` (10.0.10.0/24)
6. Guarda tokens en `/opt/distrisearch/config/swarm-tokens.env`

## Configuración de firewall integrada

El script configura automáticamente los puertos requeridos:
- Docker Swarm: 2377/tcp, 7946/tcp+udp, 4789/udp
- DistriSearch: 8001, 8081-8089, 4431-4439, 8002-8009

## En el manager principal (manual)
```bash
docker swarm init --advertise-addr 192.168.1.10
```
- `--advertise-addr`: IP accesible por otros nodos.
- Guarda el token de salida para unir workers.

## Crear red overlay (manual)
```bash
docker network create \
    --driver overlay \
    --attachable \
    --subnet 10.0.10.0/24 \
    distrisearch-network
```

## Obtener tokens
```bash
docker swarm join-token worker   # para workers
docker swarm join-token manager  # para managers adicionales
```

## Tokens guardados automáticamente
```bash
cat /opt/distrisearch/config/swarm-tokens.env
```

## Unir workers
En cada worker usar `03-join-swarm.sh` o:
```bash
docker swarm join --token SWMTKN-1-xxx... 192.168.1.10:2377
```

## Verificar
```bash
docker node ls
# ID          HOSTNAME   STATUS  AVAILABILITY  MANAGER STATUS
# abc123 *    manager1   Ready   Active        Leader
# def456      worker1    Ready   Active
# ghi789      worker2    Ready   Active
```

## Alta disponibilidad de managers
Para tolerancia a 1 fallo, usar 3 managers; para 2 fallos, 5 managers.
```bash
docker swarm join --token <manager-token> 192.168.1.10:2377
```