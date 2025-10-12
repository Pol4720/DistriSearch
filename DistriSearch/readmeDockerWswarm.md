# Docker Swarm (modo centralizado) — Guía rápida

Este archivo es una guía breve. Para la guía completa consulta `README_DockerSwarm.md` en la raíz de `DistriSearch`.

## ¿Qué es Docker Swarm?

Orquestador nativo de Docker para desplegar y mantener servicios (contenedores) en un clúster. Permite redes overlay, actualizaciones escalonadas y reinicios automáticos.

## ¿Para qué lo usamos?

Esta primera revisión corre en modo centralizado: un backend que indexa una carpeta compartida y un frontend que consulta al backend. No necesitas agentes todavía.

## Pasos básicos (Windows PowerShell)

1) Inicializa Swarm (una sola vez):

```powershell
docker swarm init
```

2) Construye imágenes locales (opcional si no usas un registry):

```powershell
docker build -t distrisearch/backend:latest .\DistriSearch\backend

docker build -t distrisearch/frontend:latest .\DistriSearch\frontend
```

3) Despliega el stack:

```powershell
cd .\DistriSearch\deploy

docker stack deploy -c docker-stack.yml distrisearch
```

4) Accede a la app:
- Backend: http://localhost:8000/docs
- Frontend: http://localhost:8501

El backend hará auto-scan de la carpeta `/app/central_shared` si `CENTRAL_AUTO_SCAN=true` (ya configurado en el stack).

5) Cargar archivos en `central_shared` (volumen Docker):

```powershell
$cid = docker create -v central_shared:/data alpine:3.19 sh

docker cp .\central_shared\ $cid:/data/

docker rm $cid
```

6) Actualizar el stack tras cambios:

```powershell
docker stack deploy -c docker-stack.yml distrisearch
```

7) Eliminar el stack:

```powershell
docker stack rm distrisearch
```

## Cambios hechos en el código

- `backend/database.py`: `DATABASE_PATH` por variable de entorno y creación de directorios.
- `backend/main.py`: auto-scan opcional al inicio (también en evento startup).
- `backend/Dockerfile`: crea `/app/data` y `/app/central_shared`.
- `deploy/docker-stack.yml`: stack simplificado (backend + frontend), volúmenes y variables de entorno.
- `frontend` usa `DISTRISEARCH_BACKEND_URL` para localizar el backend en Swarm.

Más detalles en `README_DockerSwarm.md`.
