# Docker Swarm — Comandos útiles (DistriSearch, modo centralizado)

Archivos relevantes:

- Stack: [DistriSearch/deploy/docker-stack.yml](../deploy/docker-stack.yml)
- Frontend: [DistriSearch/frontend/app.py](../frontend/app.py), [DistriSearch/frontend/Dockerfile](../frontend/Dockerfile)
- Backend: [DistriSearch/backend/Dockerfile](../backend/Dockerfile)

## 1) Construir imágenes locales

- Construir la imagen del backend (para usar en el stack):

```powershell
docker build -t distrisearch/backend:latest .\DistriSearch\backend
```

- Construir la imagen del frontend (incluye secrets.toml vacío en la imagen):

```powershell
docker build -t distrisearch/frontend:latest .\DistriSearch\frontend
```

Para qué sirve: empaqueta tu código y dependencias en imágenes Docker etiquetadas como `latest`, que el stack usará al desplegar.

## 2) Inicializar Docker Swarm (una vez)

- Iniciar el modo Swarm en tu máquina:

```powershell
docker swarm init
```

Para qué sirve: habilita el orquestador de Docker para poder desplegar stacks/servicios.

## 3) Desplegar/actualizar el stack

- Desplegar (o actualizar) el stack con el YAML:

```powershell
cd .\DistriSearch\deploy
docker stack deploy -c docker-stack.yml distrisearch
```

Para qué sirve: crea o actualiza los servicios `backend` y `frontend` definidos en el stack. Realiza rolling updates si detecta cambios.

Nota: El aviso “image ... could not be accessed on a registry” es normal usando imágenes locales en un único nodo.

## 4) Abrir la aplicación

- Frontend (Streamlit): http://localhost:8501
- Backend (FastAPI docs): http://localhost:8000/docs

## 5) Comprobar estado de los servicios

- Ver servicios del stack y sus puertos:

```powershell
docker stack services distrisearch
```

- Ver tareas/replicas y su estado:

```powershell
docker stack ps distrisearch
```

Para qué sirve: diagnosticar si los servicios están corriendo y expuestos correctamente.

## 6) Ver logs

- Seguir logs del frontend:

```powershell
docker service logs distrisearch_frontend --follow
```

- Seguir logs del backend:

```powershell
docker service logs distrisearch_backend --follow
```

Para qué sirve: revisar el arranque y posibles errores en tiempo real.

## 7) Forzar un redeploy (si mantienes misma etiqueta)

- Forzar recreación del frontend sin cambiar nada más:

```powershell
docker service update --force distrisearch_frontend
```

- Forzar recreación del backend:

```powershell
docker service update --force distrisearch_backend
```

Para qué sirve: si vuelves a etiquetar como `latest` y Swarm no detecta cambios, esto reinicia las tareas con la imagen disponible en el nodo.

## 8) Gestionar el volumen central (cargar archivos)

- Crear contenedor temporal con el volumen `central_shared` montado:

```powershell
$cid = docker create -v central_shared:/data alpine:3.19 sh
```

- Copiar una carpeta local al volumen:

```powershell
docker cp .\central_shared\ $cid:/data/
```

- Eliminar el contenedor temporal:

```powershell
docker rm $cid
```

Para qué sirve: pre-cargar archivos a indexar en el volumen `central_shared` usado por el backend.

Comandos útiles de volúmenes:

```powershell
docker volume ls
docker volume inspect central_shared
```

## 9) Limpiar

- Eliminar el stack (detiene y borra servicios/redes del stack):

```powershell
docker stack rm distrisearch
```

- Listar imágenes locales:

```powershell
docker image ls
```

- Eliminar imágenes (opcional, para liberar espacio):

```powershell
docker rmi distrisearch/frontend:latest distrisearch/backend:latest
```

- Eliminar volúmenes (opcional, borra datos: ¡cuidado!):

```powershell
docker volume rm central_shared backend_data
```

## Flujo típico de actualización

1. Editar código, e.g. [frontend/app.py](../frontend/app.py)
2. Reconstruir imagen del servicio afectado:

```powershell
docker build -t distrisearch/frontend:latest .\DistriSearch\frontend
```

3. Redeploy del stack:

```powershell
cd .\DistriSearch\deploy
docker stack deploy -c docker-stack.yml distrisearch
```

4. Verificar:

```powershell
docker stack services distrisearch
docker service logs distrisearch_frontend --follow
```
