# DistriSearch: despliegue multi-equipo (Backend en PC A, Frontend en PC B)

Este documento explica dos formas de ejecutar la app centralizada en dos máquinas distintas dentro de la misma red Wi‑Fi.

- Opción 1 (rápida y recomendada en Windows): sin Swarm entre equipos. Ejecuta backend en la PC A y frontend en la PC B con `docker run`, apuntando el frontend al backend por IP LAN.
- Opción 2 (avanzada): con Docker Swarm en VMs Linux con red bridged (modo puente), formando un clúster real (manager + worker).

Ambas asumen que ya tienes Docker instalado en ambas máquinas.

---

## Opción 1: sin Swarm (rápida, funciona hoy mismo)

Objetivo: Backend en PC A, Frontend en PC B. Se comunican por IP LAN. Comandos para Windows PowerShell.

1) Preparar IPs y firewall
- En la PC A (backend): consigue tu IP LAN (IPv4) con `ipconfig` (ej. 192.168.1.X).
- Abre el firewall en la PC A para 8000/TCP (backend) y en la PC B para 8501/TCP (frontend) si vas a acceder desde otras PCs.

2) PC A (Backend)

- Construye la imagen del backend (o usa una existente):
```powershell
# Desde la raíz del repo
docker build -t distrisearch/backend:latest .\DistriSearch\backend
```

- Elige uno de estos métodos para la carpeta central:

A) Volumen Docker (persistente dentro de Docker):
```powershell
docker run -d --name distrisearch_backend --restart=unless-stopped `
  -p 8000:8000 `
  -e ENVIRONMENT=production `
  -e CENTRAL_SHARED_FOLDER=/app/central_shared `
  -e CENTRAL_AUTO_SCAN=true `
  -e DATABASE_PATH=/app/data/distrisearch.db `
  -v backend_data:/app/data `
  -v central_shared:/app/central_shared `
  distrisearch/backend:latest
```

Cargar ejemplos del repo al volumen (opcional):
```powershell
# Copia el contenido de .\central_shared al volumen central_shared
docker run --rm -v central_shared:/data -v "${PWD}\central_shared:/host:ro" `
  alpine:3.19 sh -c "cp -r /host/. /data/ && ls -la /data"
```

B) Bind mount directo a tu carpeta local (refleja cambios al instante):
```powershell
docker run -d --name distrisearch_backend --restart=unless-stopped `
  -p 8000:8000 `
  -e ENVIRONMENT=production `
  -e CENTRAL_SHARED_FOLDER=/app/central_shared `
  -e CENTRAL_AUTO_SCAN=true `
  -e DATABASE_PATH=/app/data/distrisearch.db `
  -v backend_data:/app/data `
  -v "C:\\Proyectos\\DistriSearch\\central_shared:/app/central_shared" `
  distrisearch/backend:latest
```

Verifica:
```powershell
# Reemplaza <IP_PC_A> con la IP LAN de la PC A
Start-Process "http://<IP_PC_A>:8000/docs"
```

3) PC B (Frontend)

- Construye o carga la imagen del frontend:
```powershell
# Si tienes el repo en la PC B
docker build -t distrisearch/frontend:latest .\DistriSearch\frontend
```

Alternativa: exportar desde la PC A e importar en la PC B:
```powershell
# En PC A
docker save -o frontend.tar distrisearch/frontend:latest
# Copia frontend.tar a PC B y allí:
docker load -i .\frontend.tar
```

- Ejecuta el frontend apuntando al backend por IP LAN:
```powershell
docker run -d --name distrisearch_frontend --restart=unless-stopped `
  -p 8501:8501 `
  -e DISTRISEARCH_BACKEND_URL=http://<IP_PC_A>:8000 `
  distrisearch/frontend:latest
```

Abre la app:
```powershell
Start-Process "http://localhost:8501"
```

4) Probar escaneo y búsqueda
- En el frontend: Modo "Centralizado" → pestaña "Central" → "Escanear ahora".
- En "Buscar", escribe un término de los archivos en la carpeta central.

Notas:
- Si usas VPN (ProtonVPN u otra), puede bloquear el acceso por IP LAN. Desconéctala o crea reglas para permitir tráfico local.
- Si no ves resultados tras escanear, revisa logs del backend: `docker logs -f distrisearch_backend`.

---

## Opción 2: con Docker Swarm (en VMs Linux bridged)

En Windows con Docker Desktop, el Swarm multinodo entre máquinas físicas suele fallar por el NAT de la VM. La vía estable es usar dos VMs Linux (Ubuntu/Debian) con red bridged.

1) Preparación en ambas VMs Linux
```bash
# Instalar Docker (Ubuntu/Debian)
sudo apt-get update && sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \ 
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
```

Abrir puertos en ambos hosts: 2377/TCP, 7946/TCP+UDP, 4789/UDP.

2) Iniciar Swarm en VM A (manager)
```bash
MANAGER_IP=<IP_LAN_VM_A>
sudo docker swarm init --advertise-addr $MANAGER_IP
sudo docker swarm join-token worker
```

3) Unir VM B (worker)
```bash
WORKER_TOKEN=$(sudo docker swarm join-token -q worker)
sudo docker swarm join --token $WORKER_TOKEN <IP_LAN_VM_A>:2377
```

4) Etiquetar nodos y desplegar stack
```bash
sudo docker node ls
# Reemplaza con nombres reales
sudo docker node update --label-add role=backend <NODO_VM_A>
sudo docker node update --label-add role=frontend <NODO_VM_B>

# Copia el repo (o deploy/) a VM A
cd /ruta/al/repo/DistriSearch/deploy
sudo docker stack deploy -c docker-stack.yml distrisearch
sudo docker service ps distrisearch_backend
sudo docker service ps distrisearch_frontend
```

5) Cargar datos y probar
```bash
# Copiar ejemplos al volumen central_shared del nodo backend
sudo docker run --rm -v central_shared:/data -v /ruta/local/central_shared:/host:ro alpine:3.19 \
  sh -c "cp -r /host/. /data/ && ls -la /data"
```
- Frontend: http://<IP_VM_B>:8501
- Backend: http://<IP_VM_A>:8000/docs

---

## Solución de problemas

- Frontend no conecta con backend
  - Verifica DISTRISEARCH_BACKEND_URL en el contenedor frontend
  - Prueba: `curl -s http://<IP_PC_A>:8000/docs` desde dentro del contenedor frontend
  - Revisa firewall en la PC A para 8000/TCP

- Escaneo no encuentra archivos
  - La ruta en el contenedor backend debe ser `/app/central_shared`
  - Si usas volumen Docker, copia los archivos al volumen
  - Si usas bind mount, revisa que la ruta del host sea correcta y accesible

- Swarm multinodo no forma clúster
  - En Windows + Docker Desktop es habitual por NAT; usa VMs Linux bridged
  - Verifica puertos 2377/7946/4789 abiertos en ambos hosts y routers

---

## Referencias
- docker run: https://docs.docker.com/engine/reference/run/
- Docker Swarm: https://docs.docker.com/engine/swarm/
- Puertos Swarm: https://docs.docker.com/engine/swarm/swarm-tutorial/#open-the-necessary-ports
