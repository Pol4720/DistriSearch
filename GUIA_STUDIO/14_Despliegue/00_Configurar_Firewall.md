````markdown
# Configuración del Firewall

## Propósito

El script `00-configure-firewall.sh` configura los puertos necesarios para que Docker Swarm funcione correctamente, especialmente el **Routing Mesh** que requiere el puerto 4789/UDP para la red overlay VXLAN.

## Cuándo usar

Ejecutar este script en **TODOS los nodos** cuando:
- Hay problemas de conectividad entre nodos del Swarm
- Los servicios no son accesibles desde otros nodos
- El Routing Mesh no funciona correctamente
- Los contenedores no pueden comunicarse entre nodos

## Tipos de firewall soportados

El script detecta automáticamente qué firewall está instalado:

| Firewall | Distribuciones |
|----------|---------------|
| UFW | Ubuntu, Debian |
| firewalld | RHEL, CentOS, Fedora |
| iptables | Fallback universal |

## Puertos configurados

### Docker Swarm (obligatorios)
```
2377/tcp   - Gestión del cluster Swarm
7946/tcp   - Comunicación entre nodos
7946/udp   - Comunicación entre nodos
4789/udp   - Red overlay VXLAN (CRÍTICO para Routing Mesh)
```

### DistriSearch
```
8001/tcp       - Master API
8081-8089/tcp  - Slave HTTP (Frontend Nginx)
4431-4439/tcp  - Slave HTTPS (Frontend Nginx)
8002-8009/tcp  - Slave API (Backend FastAPI)
```

### Servicios internos (solo red privada)
```
27017/tcp  - MongoDB (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
6379/tcp   - Redis (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
```

## Ejecución

```bash
# Requiere permisos de root
sudo ./00-configure-firewall.sh
```

## Ejemplo de salida

```
==============================================
  DistriSearch - Configurar Firewall
==============================================

Puertos que se configurarán:

  Docker Swarm:
    - 2377/tcp  : Gestión del cluster
    - 7946/tcp  : Comunicación entre nodos
    - 7946/udp  : Comunicación entre nodos
    - 4789/udp  : Red overlay (VXLAN) - CRÍTICO para routing mesh

  DistriSearch:
    - 8001/tcp  : Master API
    - 8081-8089 : Slave HTTP (Frontend)
    - 4431-4439 : Slave HTTPS (Frontend)
    - 8002-8009 : Slave API (Backend)

[INFO] Configurando UFW...
[INFO] UFW configurado correctamente

[INFO] Verificando puertos...

  ✓ Puerto 2377 (Swarm Management) - Escuchando
  ○ Puerto 8001 (Master API) - No hay servicio escuchando

==============================================
  Firewall Configurado
==============================================
```

## Integración con scripts 02 y 03

Los scripts `02-init-swarm.sh` y `03-join-swarm.sh` **ya incluyen** configuración automática del firewall. El script `00-configure-firewall.sh` es útil para:

1. Diagnóstico de problemas de red
2. Verificación manual de puertos
3. Nodos que tuvieron problemas iniciales

## Troubleshooting

### El Routing Mesh no funciona
```bash
# 1. Ejecutar en TODOS los nodos
sudo ./00-configure-firewall.sh

# 2. Reiniciar Docker
sudo systemctl restart docker

# 3. Verificar la red overlay
docker network inspect distrisearch-network

# 4. Probar conectividad UDP
nc -zuv <otro-nodo> 4789
```

### Verificar reglas aplicadas
```bash
# UFW
sudo ufw status numbered

# iptables
sudo iptables -L INPUT -n --line-numbers

# firewalld
sudo firewall-cmd --list-all
```
````
