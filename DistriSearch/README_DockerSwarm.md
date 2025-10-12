# Docker Swarm: qué es, para qué se usa y cómo ejecutar DistriSearch (modo centralizado)

Este documento explica de forma sencilla qué es Docker Swarm, por qué lo usamos en esta primera revisión del proyecto y los pasos para desplegar DistriSearch en modo centralizado usando Docker Swarm.

## ¿Qué es Docker Swarm?

- Es la orquestación nativa de Docker para ejecutar múltiples contenedores distribuidos en uno o varios servidores como si fueran un “cluster”.
- Facilita el despliegue, escalado y actualización de servicios (contenedores) declarados en un archivo de stack (`docker-stack.yml`).
- Ofrece redes overlay, balanceo interno y reinicio automático de servicios si fallan.

En resumen: con Swarm puedes “subir” tu aplicación compuesta de varios servicios (backend, frontend, etc.) y Swarm se encarga de mantenerlos corriendo.

## ¿Para qué lo usamos aquí?

En la primera revisión, vamos a correr DistriSearch en modo centralizado: un único backend que indexa una carpeta compartida “central” y un frontend que habla con ese backend. Swarm nos da:
- Despliegue sencillo con un solo comando.
- Reinicios automáticos si algún servicio falla.
- Base para crecer a un despliegue distribuido con agentes en el futuro.

## Cambios realizados en el proyecto

1. backend/database.py
   - La ruta de la base de datos ahora es configurable con la variable de entorno `DATABASE_PATH` (por defecto `distrisearch.db`). Esto permite persistir la BD en un volumen.
   - Se crea el directorio contenedor de la base de datos si no existe.

2. backend/main.py
   - Se añadió un “auto-scan” opcional del repositorio central al arrancar si `CENTRAL_AUTO_SCAN=true` (usa `CENTRAL_SHARED_FOLDER` o `./central_shared`).
   - También se ejecuta en el evento de inicio de FastAPI para cubrir el modo de despliegue con workers.

3. backend/Dockerfile
   - Se crean los directorios `/app/data` y `/app/central_shared` dentro de la imagen (pueden montarse como volúmenes al ejecutar).

4. deploy/docker-stack.yml
   - Simplificado para modo centralizado: solo `backend` y `frontend`.
   - Variables de entorno para carpeta central, BD y auto-scan.
   - Volúmenes para persistir la base de datos y la carpeta compartida central.
   - Red overlay `distrisearch_network` para que los servicios se descubran por nombre.
   - La variable usada por el frontend para localizar el backend es `DISTRISEARCH_BACKEND_URL`.

No se requieren agentes en esta primera revisión con Swarm.

## Requisitos previos

- Windows con Docker Desktop instalado y con “Docker Engine” habilitado.
- Powershell como terminal.
- Repositorio clonado localmente.

## Preparar imágenes (opcional)

Si no tienes imágenes publicadas en un registro, puedes construirlas localmente y referenciarlas con etiquetas locales. Desde la raíz del proyecto:

```powershell
# Construir imágenes locales
docker build -t distrisearch/backend:latest .\DistriSearch\backend

docker build -t distrisearch/frontend:latest .\DistriSearch\frontend
```

Asegúrate de que `deploy/docker-stack.yml` use esas etiquetas (ya está configurado así por defecto).

## Inicializar Docker Swarm

Solo necesitas hacerlo una vez en la máquina:

```powershell
docker swarm init
```

Si ya estaba inicializado, el comando te lo indicará y puedes continuar.

## Preparar volúmenes/carpetas (Windows)

El stack crea dos volúmenes locales:
- `backend_data`: para persistir `distrisearch.db`.
- `central_shared`: carpeta con los archivos a indexar (modo central).

Puedes pre-cargar archivos en el volumen `central_shared` copiándolos dentro del volumen tras desplegar, o cambiar el `docker-stack.yml` para usar un bind mount a una ruta de tu host. Por simplicidad, lo dejamos como volumen local gestionado por Docker.

Para inspeccionar o copiar archivos al volumen `central_shared`:

```powershell
# Crear un contenedor temporal para interactuar con el volumen central_shared
$cid = docker create -v central_shared:/data alpine:3.19 sh

# Copiar desde tu carpeta local a ese volumen (ajusta la ruta de origen)
docker cp .\central_shared\ $cid:/data/

# Eliminar el contenedor temporal (los datos quedan en el volumen)
docker rm $cid
```

Alternativamente, puedes montar una ruta del host editando `deploy/docker-stack.yml`:

```yaml
    volumes:
      - backend_data:/app/data
      - type: bind
        source: C:\\ruta\\a\\tu\\central_shared
        target: /app/central_shared
```

Ojo: para rutas de Windows en binds usa doble barra invertida en YAML.

## Desplegar el stack

Desde la carpeta `DistriSearch/deploy`:

```powershell
cd .\DistriSearch\deploy

docker stack deploy -c docker-stack.yml distrisearch
```

Esto creará los servicios `distrisearch_backend` y `distrisearch_frontend` en la red `distrisearch_network`.

Verifica el estado:

```powershell
docker stack services distrisearch
```

## Acceder a la app

- Backend (FastAPI): http://localhost:8000/docs
- Frontend (Streamlit): http://localhost:8501

El backend arranca y, si `CENTRAL_AUTO_SCAN=true`, indexará automáticamente los archivos presentes en `/app/central_shared` (el volumen `central_shared`).

Si deseas forzar un escaneo manual:

```powershell
# Escaneo explícito (opcional). Reemplaza FOLDER si quieres otra ruta dentro del contenedor.
Invoke-WebRequest -UseBasicParsing -Method POST `
    -Uri http://localhost:8000/central/scan `
    -ContentType 'application/json' `
    -Body '{"folder": "/app/central_shared"}'
```

## Actualizar el stack

Si reconstruyes imágenes o cambias el YAML:

```powershell
docker stack deploy -c docker-stack.yml distrisearch
```

Swarm aplicará rolling update según la política del servicio.

## Limpiar

Para eliminar el stack completo:

```powershell
docker stack rm distrisearch
```

Si quieres, también puedes eliminar los volúmenes (perderás los datos):

```powershell
docker volume rm distrisearch_backend_data distrisearch_central_shared
```

## Variables de entorno relevantes

- `CENTRAL_SHARED_FOLDER`: ruta dentro del contenedor del repositorio central (por defecto `/app/central_shared`).
- `CENTRAL_AUTO_SCAN`: si está en `true`, el backend escanea la carpeta central al arrancar.
- `DATABASE_PATH`: ruta del archivo SQLite (por defecto `distrisearch.db`). En el stack se mapea a `/app/data/distrisearch.db` para persistencia.

## Notas

- Esta configuración es “centralizada” (sin agentes). En una fase posterior podrás ampliar el `docker-stack.yml` para añadir servicios de agentes en nodos workers.
- En Windows, los bind mounts requieren rutas bien escapadas y compartir discos con Docker Desktop (Settings > Resources > File sharing).
- Si usas imágenes locales, no es necesario empujarlas a un registry para un Swarm de un solo nodo (manager). Para clúster con varios nodos, deberías publicar las imágenes en un registry accesible por todos los nodos.
