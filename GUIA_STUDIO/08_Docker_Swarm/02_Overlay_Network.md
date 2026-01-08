# Redes Overlay en Docker Swarm

## ¿Qué es una red overlay?
Una red virtual que abarca múltiples hosts físicos, permitiendo que contenedores en distintas máquinas se comuniquen como si estuvieran en la misma LAN.

## Configuración en DistriSearch
```yaml
networks:
  distrisearch-network:
    driver: overlay
    attachable: true
    ipam:
      config:
        - subnet: 10.0.10.0/24
```
- `driver: overlay`: habilita comunicación multi-host.
- `attachable: true`: permite conectar contenedores manuales a la red.
- Subred fija 10.0.10.0/24 evita colisiones y facilita reglas de firewall.

## Ingress network
Red overlay especial para el routing mesh; recibe tráfico publicado en puertos (80/443) y lo enruta internamente al servicio.

## Comunicación entre servicios
- Los contenedores resuelven nombres de servicio ("master", "mongodb") vía DNS interno 127.0.0.11.
- El tráfico viaja cifrado (VXLAN) entre hosts; dentro de la overlay es transparente.

## Aislamiento y seguridad
- Sólo contenedores conectados a `distrisearch-network` pueden alcanzarse.
- Ingress expone únicamente puertos publicados; el resto permanece privado.
- Secrets nunca se escriben en disco, sólo en memoria del contenedor.