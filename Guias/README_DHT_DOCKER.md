# 🐳 DistriSearch con DHT en Docker Compose

Esta guía explica cómo desplegar DistriSearch con el servicio DHT usando Docker Compose.

## 📋 Requisitos Previos

- Docker Desktop instalado y ejecutándose
- Docker Compose (incluido con Docker Desktop)
- Puertos disponibles: 8000, 8080, 8501, 2000, 8081, 8082

## 🚀 Inicio Rápido

### 1. Configurar Variables de Entorno

```powershell
# Desde la carpeta deploy/
cd DistriSearch\deploy
cp .env.example .env
```

Edita `.env` y ajusta tu IP de red:

```env
EXTERNAL_IP=192.168.1.100  # Tu IP de red local
PUBLIC_URL=http://192.168.1.100:8000
DHT_AUTO_START=true
DHT_MODE=external
```

### 2. Arrancar los Servicios

```powershell
docker-compose up -d --build
```

Esto iniciará:
- **dht**: Servicio DHT (puerto 8080 HTTP, 2000 P2P)
- **backend**: API DistriSearch (puerto 8000)
- **frontend**: UI Streamlit (puerto 8501)
- **agent1** y **agent2**: Agentes de archivos (puertos 8081, 8082)

### 3. Verificar el Estado

```powershell
# Ver logs
docker-compose logs -f

# Ver solo logs de DHT
docker-compose logs -f dht

# Ver estado de contenedores
docker-compose ps
```

### 4. Acceder a la Aplicación

- **Frontend**: http://localhost:8501
- **Backend API**: http://localhost:8000/docs
- **DHT API**: http://localhost:8080/server/rest/DHT/imprimirSucPred

## 🔧 Configuración Avanzada

### Modo DHT Inproc (DHT dentro del backend)

Si prefieres ejecutar DHT dentro del proceso del backend (un solo contenedor):

Edita `.env`:

```env
DHT_AUTO_START=true
DHT_MODE=inproc
DHT_PORT=2000
```

Y comenta el servicio `dht` en `docker-compose.yml`:

```yaml
services:
  # dht:  # Comentar este servicio completo si usas inproc
  #   ...
  
  backend:
    # ... configuración existente ...
    # depends_on:
    #   - dht  # Comentar esta línea también
```

### Red Multi-Nodo DHT

Para crear una red DHT con múltiples backends:

**Nodo 1 (seed):**

```yaml
# docker-compose.yml
services:
  backend:
    environment:
      - DHT_AUTO_START=true
      - DHT_MODE=inproc
      - DHT_PORT=2000
      # Sin DHT_SEED_IP (es el seed)
```

**Nodo 2 (se une al seed):**

```yaml
# docker-compose.yml (en otra máquina o con puertos diferentes)
services:
  backend:
    ports:
      - "8001:8000"  # Puerto diferente
    environment:
      - DHT_AUTO_START=true
      - DHT_MODE=inproc
      - DHT_PORT=2001
      - DHT_SEED_IP=192.168.1.10  # IP del nodo 1
      - DHT_SEED_PORT=2000
```

## 📊 Verificar la DHT

### Desde el Host

```powershell
# Ver sucesor y predecesor
Invoke-RestMethod -Uri "http://localhost:8080/server/rest/DHT/imprimirSucPred"

# Ver finger table
Invoke-RestMethod -Uri "http://localhost:8080/server/rest/DHT/imprimirFingerTable"
```

### Desde el Frontend

1. Navega a http://localhost:8501
2. Ve a **🌐 Nodos** → **⚙️ Configuración Avanzada**
3. Expande **🧩 DHT (Red Distribuida)**
4. Usa los controles para:
   - Ver estado de la DHT
   - Subir/descargar archivos de prueba
   - Unirse a otras redes

### Desde la API del Backend

```powershell
# Obtener estado DHT
Invoke-RestMethod -Uri "http://localhost:8000/dht/sucpred"

# Subir archivo de prueba
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/dht/upload?filename=test.txt&data=HolaDHT"

# Descargar archivo
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/dht/download?filename=test.txt"
```

## 🛠️ Comandos Útiles

### Gestión de Contenedores

```powershell
# Iniciar servicios
docker-compose up -d

# Detener servicios
docker-compose down

# Reiniciar un servicio específico
docker-compose restart backend

# Ver logs en tiempo real
docker-compose logs -f backend dht

# Reconstruir imágenes
docker-compose up -d --build

# Escalar agentes (crear más réplicas)
docker-compose up -d --scale agent1=3
```

### Inspección y Debug

```powershell
# Ejecutar comando dentro del contenedor backend
docker-compose exec backend bash

# Ver variables de entorno del backend
docker-compose exec backend env | grep DHT

# Inspeccionar red Docker
docker network inspect deploy_distrisearch_network

# Ver procesos en el contenedor DHT
docker-compose exec dht ps aux
```

### Limpieza

```powershell
# Detener y eliminar contenedores + volúmenes
docker-compose down -v

# Eliminar imágenes no usadas
docker image prune -a

# Limpieza completa (¡cuidado!)
docker system prune -a --volumes
```

## 📁 Estructura de Volúmenes

Los siguientes volúmenes persisten datos:

- `backend_data`: Base de datos y archivos del backend
- `./shared_folders/agent1`: Archivos compartidos del agente 1
- `./shared_folders/agent2`: Archivos compartidos del agente 2
- `../../certs`: Certificados SSL (montado read-only)

Para hacer backup:

```powershell
# Backup de volumen backend_data
docker run --rm -v deploy_backend_data:/data -v ${PWD}:/backup busybox tar czf /backup/backend_backup.tar.gz /data
```

## 🔒 HTTPS con Docker

### 1. Generar Certificados

```powershell
# Desde la raíz del proyecto
cd DistriSearch\scripts
.\generate_ssl_certs.ps1 -Hostname 192.168.1.100
```

### 2. Actualizar .env

```env
ENABLE_SSL=true
AGENT_SSL_ENABLED=true
PUBLIC_URL=https://192.168.1.100:8000
DISTRISEARCH_BACKEND_PUBLIC_URL=https://192.168.1.100:8000
```

### 3. Reiniciar Servicios

```powershell
cd ..\deploy
docker-compose down
docker-compose up -d --build
```

## 🌐 Acceso desde Red Externa

### Configurar Firewall (Windows)

```powershell
# Permitir puertos en el firewall
New-NetFirewallRule -DisplayName "DistriSearch Backend" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "DistriSearch DHT HTTP" -Direction Inbound -LocalPort 8080 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "DistriSearch DHT P2P" -Direction Inbound -LocalPort 2000 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "DistriSearch Frontend" -Direction Inbound -LocalPort 8501 -Protocol TCP -Action Allow
```

### Verificar desde Otra Máquina

```powershell
# Desde otra máquina en la red
Invoke-RestMethod -Uri "http://192.168.1.100:8000/health"
Invoke-RestMethod -Uri "http://192.168.1.100:8080/server/rest/DHT/imprimirSucPred"
```

## 🐛 Troubleshooting

### DHT no arranca

**Problema:** El contenedor DHT se reinicia constantemente.

**Solución:**
```powershell
# Ver logs detallados
docker-compose logs dht

# Verificar puertos
netstat -ano | findstr ":8080"
netstat -ano | findstr ":2000"

# Reiniciar con logs en tiempo real
docker-compose restart dht && docker-compose logs -f dht
```

### Backend no puede conectar con DHT

**Problema:** Error "Connection refused" desde el backend.

**Solución:**
1. Verifica que el servicio DHT esté corriendo:
   ```powershell
   docker-compose ps dht
   ```

2. Verifica la conectividad de red:
   ```powershell
   docker-compose exec backend ping dht
   docker-compose exec backend curl http://dht:8080/server/rest/DHT/imprimirSucPred
   ```

3. Verifica las variables de entorno:
   ```powershell
   docker-compose exec backend env | grep DHT
   ```

### Problemas de Permisos con Volúmenes

**Problema:** Errores al escribir en `shared_folders`.

**Solución:**
```powershell
# Windows: ajustar permisos de carpeta
icacls ".\shared_folders" /grant Everyone:F /T

# O ejecutar Docker Desktop como administrador
```

### Puerto Ya en Uso

**Problema:** "port is already allocated".

**Solución:**
```powershell
# Identificar proceso usando el puerto
netstat -ano | findstr :8000

# Detener el proceso
taskkill /PID <PID> /F

# O cambiar el puerto en docker-compose.yml
ports:
  - "8001:8000"  # Mapear a puerto diferente
```

### Healthcheck Falla

**Problema:** El contenedor DHT reporta "unhealthy".

**Solución:**
```powershell
# Ver resultado del healthcheck
docker inspect --format='{{json .State.Health}}' distrisearch-dht | jq

# Ejecutar healthcheck manualmente
docker-compose exec dht python -c "import requests; print(requests.get('http://localhost:8080/server/rest/DHT/imprimirSucPred').text)"
```

## 📚 Referencias

- [Documentación DHT](../DHT_INTEGRATION_GUIDE.md)
- [Documentación Docker Compose](https://docs.docker.com/compose/)
- [Comandos Docker Swarm](../readme_Comandos_DockerSwarm.md)

## 🎯 Checklist de Despliegue

- [ ] `.env` configurado con IP correcta
- [ ] Puertos 8000, 8080, 8501, 2000 disponibles
- [ ] Docker Desktop ejecutándose
- [ ] `docker-compose up -d --build` ejecutado sin errores
- [ ] `docker-compose ps` muestra todos los servicios "Up"
- [ ] Frontend accesible en http://localhost:8501
- [ ] Backend API accesible en http://localhost:8000/docs
- [ ] DHT responde en http://localhost:8080
- [ ] Controles DHT funcionan desde el frontend
- [ ] Firewall configurado para acceso externo (si aplica)

---

**¡Listo!** Ahora tienes DistriSearch con DHT corriendo en Docker Compose. 🎉
