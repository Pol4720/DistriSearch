# 🧩 Guía de Integración DHT con DistriSearch

Esta guía te ayudará a configurar y usar la implementación DHT (Distributed Hash Table) con el buscador distribuido DistriSearch.

## 📋 Tabla de Contenidos

- [Descripción General](#descripción-general)
- [Modos de Operación](#modos-de-operación)
- [Configuración](#configuración)
- [Inicio Rápido](#inicio-rápido)
- [Variables de Entorno](#variables-de-entorno)
- [Uso desde Frontend](#uso-desde-frontend)
- [API REST](#api-rest)
- [Docker Compose](#docker-compose)
- [Troubleshooting](#troubleshooting)

---

## 📖 Descripción General

La integración DHT permite:
- Almacenar y buscar archivos de forma distribuida usando una Chord DHT
- Conectar múltiples nodos en una red P2P
- Replicar archivos automáticamente entre nodos
- Tolerancia a fallos: los nodos pueden entrar/salir dinámicamente

### Arquitectura

```
Frontend (Streamlit)
       ↓
Backend (FastAPI) ← wrapper DHT service
       ↓
[Modo External]    [Modo Inproc]
       ↓                  ↓
Flask DHT API      DHT Peer (in-process)
```

---

## 🎯 Modos de Operación

### 1. **Modo External** (Recomendado para desarrollo)

El backend se comunica con un servicio DHT independiente (Flask app) vía HTTP.

**Ventajas:**
- Separación de responsabilidades
- Fácil debugging
- Puede ejecutarse en máquinas diferentes

**Cuándo usar:**
- Desarrollo local
- Testing
- Múltiples instancias DHT independientes

### 2. **Modo Inproc** (Para producción/despliegues simples)

El backend importa e inicia un Peer DHT dentro del mismo proceso.

**Ventajas:**
- Un solo proceso/contenedor
- Menor overhead de red
- Configuración simplificada

**Cuándo usar:**
- Despliegue en producción
- Contenedores Docker
- Recursos limitados

---

## ⚙️ Configuración

### Opción A: Modo External

1. **Arranca el servicio DHT (Flask):**

```powershell
# Desde la raíz del proyecto
cd DHT
python main.py
```

El servicio escuchará en `http://0.0.0.0:8080`

2. **Configura el backend:**

Crea/edita `backend/.env`:

```env
DHT_AUTO_START=true
DHT_MODE=external
DHT_HTTP_URL=http://127.0.0.1:8080
```

3. **Arranca el backend:**

```powershell
cd DistriSearch\backend
uvicorn main:app --reload --port 8000
```

### Opción B: Modo Inproc

1. **Configura el backend:**

Crea/edita `backend/.env`:

```env
DHT_AUTO_START=true
DHT_MODE=inproc
DHT_PORT=2000
DHT_MAX_BITS=10
```

2. **Arranca el backend:**

```powershell
cd DistriSearch\backend
uvicorn main:app --reload --port 8000
```

El backend importará y arrancará un Peer DHT automáticamente.

---

## 🚀 Inicio Rápido

### Escenario 1: Red DHT de 3 nodos (Modo External)

**Terminal 1 - Nodo DHT 1 (seed):**
```powershell
cd DHT
$env:PORT = "2000"
python main.py
```

**Terminal 2 - Nodo DHT 2:**
```powershell
cd DHT
# Edita main.py para usar puerto 2001, o copia y modifica
python main.py
# Luego únete al seed vía HTTP:
# GET http://localhost:8081/server/rest/DHT/addNode?ip=<IP_SEED>
```

**Terminal 3 - Backend DistriSearch:**
```powershell
cd DistriSearch\backend
$env:DHT_AUTO_START = "true"
$env:DHT_MODE = "external"
$env:DHT_HTTP_URL = "http://127.0.0.1:8080"
$env:DHT_SEED_IP = "<IP_SEED>"  # Opcional: auto-join
uvicorn main:app --reload --port 8000
```

**Terminal 4 - Frontend:**
```powershell
cd DistriSearch\frontend
streamlit run app.py
```

### Escenario 2: Backend con DHT Inproc (single process)

**Terminal 1 - Backend:**
```powershell
cd DistriSearch\backend
$env:DHT_AUTO_START = "true"
$env:DHT_MODE = "inproc"
$env:DHT_PORT = "2000"
uvicorn main:app --reload --port 8000
```

**Terminal 2 - Frontend:**
```powershell
cd DistriSearch\frontend
streamlit run app.py
```

---

## 🔧 Variables de Entorno

Añade estas variables en `backend/.env`:

| Variable | Valores | Default | Descripción |
|----------|---------|---------|-------------|
| `DHT_AUTO_START` | `true`/`false` | `false` | Auto-iniciar DHT al arrancar backend |
| `DHT_MODE` | `external`/`inproc` | `external` | Modo de operación DHT |
| `DHT_HTTP_URL` | URL | `http://127.0.0.1:8080` | URL servicio DHT externo (modo external) |
| `DHT_PORT` | Puerto | `2000` | Puerto Peer DHT (modo inproc) |
| `DHT_BUFFER` | Bytes | `4096` | Buffer size para DHT |
| `DHT_MAX_BITS` | Entero | `10` | Bits del hash space (2^10 = 1024 nodos max) |
| `DHT_SEED_IP` | IP | (vacío) | Auto-join a seed al iniciar |
| `DHT_SEED_PORT` | Puerto | `2000` | Puerto del seed |

---

## 💻 Uso desde Frontend

### Página de Nodos

Navega a **🌐 Nodos** → **⚙️ Configuración Avanzada** → **🧩 DHT (Red Distribuida)**

**Controles disponibles:**

1. **▶️ Iniciar DHT (backend)**
   - Inicia el servicio DHT en el backend
   - Respeta la configuración `DHT_MODE`

2. **🔗 Unirse a red DHT (seed)**
   - Conecta tu nodo a una red existente
   - Requiere IP y puerto del seed

3. **📡 Estado DHT / Finger table**
   - Visualiza la finger table del nodo
   - Muestra sucesor y predecesor

4. **📁 Subir / Descargar archivo (prueba)**
   - Prueba rápida de upload/download
   - Útil para verificar conectividad

---

## 🌐 API REST

El backend expone los siguientes endpoints DHT:

### POST `/dht/start`
Inicia el servicio DHT.

**Respuesta:**
```json
{
  "status": "started",
  "mode": "inproc"
}
```

### POST `/dht/join`
Une el nodo a una red DHT existente.

**Query params:**
- `seed_ip`: IP del nodo seed
- `seed_port`: Puerto del seed (opcional)

**Respuesta:**
```json
{
  "result": "Se ha unido el nodo..."
}
```

### POST `/dht/upload`
Sube un archivo a la DHT.

**Query params:**
- `filename`: Nombre del archivo
- `data`: Contenido del archivo

**Respuesta:**
```json
{
  "result": "Se ha subido el archivo..."
}
```

### POST `/dht/download`
Descarga un archivo de la DHT.

**Query params:**
- `filename`: Nombre del archivo

**Respuesta:**
```json
{
  "result": "Contenido del archivo..."
}
```

### GET `/dht/finger`
Obtiene la finger table del nodo.

**Respuesta:**
```json
{
  "finger": {
    "123": [456, ["192.168.1.10", 2000]],
    ...
  }
}
```

### GET `/dht/sucpred`
Obtiene sucesor y predecesor del nodo.

**Respuesta:**
```json
{
  "sucpred": {
    "id": 789,
    "sucesor": ["192.168.1.11", 2000],
    "predecesor": ["192.168.1.9", 2000]
  }
}
```

---

## 🐳 Docker Compose

### Añadir servicio DHT

Edita `deploy/docker-compose.yml`:

```yaml
services:
  # ... otros servicios ...

  dht:
    build:
      context: ../DHT
      dockerfile: Dockerfile
    container_name: distrisearch-dht
    ports:
      - "8080:8080"  # HTTP API
      - "2000:2000"  # Peer socket
    networks:
      - distrisearch-net
    restart: unless-stopped

  backend:
    # ... configuración existente ...
    environment:
      - DHT_AUTO_START=true
      - DHT_MODE=external
      - DHT_HTTP_URL=http://dht:8080
    depends_on:
      - dht
```

### Dockerfile para DHT

Crea `DHT/Dockerfile`:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080 2000

CMD ["python", "main.py"]
```

---

## 🔍 Troubleshooting

### Error: "No se pudo importar DHT.peer"

**Causa:** El módulo DHT no está en el PYTHONPATH.

**Solución:**
1. Ejecuta el backend desde la raíz del proyecto:
   ```powershell
   cd E:\Proyectos\DistriSearch
   python -m uvicorn DistriSearch.backend.main:app --reload
   ```

2. O añade PYTHONPATH manualmente:
   ```powershell
   $env:PYTHONPATH = "E:\Proyectos\DistriSearch;$env:PYTHONPATH"
   cd DistriSearch\backend
   uvicorn main:app --reload
   ```

### Error: "Port already in use"

**Causa:** El puerto DHT (2000 o 8080) ya está ocupado.

**Solución:**
1. Cambia el puerto en las variables de entorno
2. O cierra el proceso que lo está usando:
   ```powershell
   netstat -ano | findstr :2000
   taskkill /PID <PID> /F
   ```

### Error: "Connection refused" al unirse a seed

**Causa:** El nodo seed no está ejecutándose o es inaccesible.

**Solución:**
1. Verifica que el seed esté corriendo: `curl http://<seed_ip>:8080/server/rest/DHT/imprimirSucPred`
2. Verifica firewall/red
3. Usa la IP de red local, no `127.0.0.1` ni `localhost`

### Los archivos no se encuentran al descargar

**Causa:** El archivo se subió a un nodo diferente o el hash no coincide.

**Solución:**
1. Verifica que el nodo que tiene el archivo esté online
2. Revisa la finger table para ver la topología de la red
3. El nombre del archivo debe ser exactamente igual (case-sensitive)

### Frontend no puede conectar con DHT

**Causa:** El backend no tiene DHT iniciada o hay error de configuración.

**Solución:**
1. Verifica que `DHT_AUTO_START=true` o inicia manualmente desde la UI
2. Revisa los logs del backend: busca "DHT iniciada en modo..."
3. Prueba directamente la API: `curl http://localhost:8000/dht/sucpred`

---

## 📚 Recursos Adicionales

- **Documentación Chord DHT:** [Paper original de Chord](https://pdos.csail.mit.edu/papers/chord:sigcomm01/chord_sigcomm.pdf)
- **Código fuente DHT:** `DHT/peer.py`
- **Endpoints backend:** `backend/routes/dht.py`
- **Servicio wrapper:** `backend/services/dht_service.py`

---

## 🎓 Ejemplos de Uso

### Ejemplo 1: Red DHT local para testing

```powershell
# Terminal 1: Backend con DHT inproc
cd DistriSearch\backend
$env:DHT_AUTO_START = "true"
$env:DHT_MODE = "inproc"
uvicorn main:app --reload

# Terminal 2: Frontend
cd DistriSearch\frontend
streamlit run app.py

# Desde el navegador:
# 1. Abre http://localhost:8501
# 2. Ve a 🌐 Nodos → Configuración Avanzada → DHT
# 3. Click en "▶️ Iniciar DHT (backend)"
# 4. Sube un archivo de prueba
# 5. Descárgalo
```

### Ejemplo 2: Conectar 2 backends en red DHT

```powershell
# Máquina 1 (192.168.1.10) - Backend A (seed)
cd DistriSearch\backend
$env:DHT_AUTO_START = "true"
$env:DHT_MODE = "inproc"
$env:DHT_PORT = "2000"
uvicorn main:app --host 0.0.0.0 --port 8000

# Máquina 2 (192.168.1.11) - Backend B
cd DistriSearch\backend
$env:DHT_AUTO_START = "true"
$env:DHT_MODE = "inproc"
$env:DHT_PORT = "2001"
$env:DHT_SEED_IP = "192.168.1.10"
$env:DHT_SEED_PORT = "2000"
uvicorn main:app --host 0.0.0.0 --port 8001
```

Ahora ambos nodos están en la misma red DHT y pueden compartir archivos.

---

## ✅ Checklist de Setup

- [ ] DHT implementación disponible en carpeta `DHT/`
- [ ] Variables de entorno configuradas en `backend/.env`
- [ ] Backend puede importar módulo DHT (PYTHONPATH correcto)
- [ ] Puerto DHT (2000) está libre
- [ ] Puerto API DHT (8080) está libre si usas external
- [ ] Backend arranca sin errores
- [ ] Frontend puede conectar con backend
- [ ] Puedes ver controles DHT en página de Nodos
- [ ] Iniciar DHT funciona desde UI
- [ ] Puedes unirte a un seed (si hay red existente)
- [ ] Subir/descargar archivos funciona

---

**¡Listo!** Ahora tienes una red DHT completamente integrada con DistriSearch. 🎉

Para soporte o dudas, revisa los logs del backend y consulta la sección de Troubleshooting.
