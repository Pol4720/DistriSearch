# 🌐 Solución de Problemas de URLs de Descarga en Red

## El Problema

Cuando DistriSearch se expone en una red local y se accede desde otra computadora, los enlaces de descarga mostraban `localhost` en lugar de una IP accesible, causando que las descargas fallaran.

### Ejemplo del error:

```
Usuario en PC1 (192.168.1.100): Ejecuta DistriSearch
Usuario en PC2 (192.168.1.101): Abre el navegador y va a http://192.168.1.100:8501
Usuario busca un archivo → Click en "Descargar"
❌ ERROR: El enlace muestra http://localhost:8000/download/file/abc123
```

## La Solución Implementada

Se implementó un sistema de **detección automática de IP pública** con priorización de configuración manual:

### 1. Detección de URL Pública (`download.py`)

```python
def get_public_base_url(request: Request) -> str:
    """
    Prioridad:
    1. Variable de entorno PUBLIC_URL
    2. Headers X-Forwarded-* (proxy/load balancer)
    3. Detección automática con IP externa
    """
```

### 2. Configuración en Backend

El backend ahora:
- ✅ Detecta automáticamente la IP local de la máquina
- ✅ Usa `PUBLIC_URL` si está configurada (más confiable)
- ✅ Reemplaza hostnames internos (localhost, backend, 0.0.0.0) por IP externa
- ✅ Soporta protocolo HTTPS automáticamente

### 3. Variables de Entorno Clave

**Backend** (`backend/.env`):
```bash
# URL pública accesible desde la red
PUBLIC_URL=https://192.168.1.100:8000

# IP externa de esta máquina
EXTERNAL_IP=192.168.1.100

# Habilitar HTTPS
ENABLE_SSL=true
```

**Frontend** (`frontend/.env`):
```bash
# URL del backend (para comunicación interna)
DISTRISEARCH_BACKEND_URL=https://192.168.1.100:8000

# URL pública para enlaces de descarga
DISTRISEARCH_BACKEND_PUBLIC_URL=https://192.168.1.100:8000
```

## Cómo Funciona Ahora

### Antes (❌ Roto):

1. Request llega al backend desde otra PC
2. `request.base_url` = `http://localhost:8000`
3. URL generada: `http://localhost:8000/download/file/abc123`
4. Frontend muestra ese enlace al usuario
5. Usuario hace click → **ERROR** (localhost no es accesible desde otra PC)

### Después (✅ Funciona):

1. Request llega al backend desde otra PC
2. `get_public_base_url()` verifica `PUBLIC_URL` env var
3. Si no existe, detecta IP externa automáticamente
4. Reemplaza hostname interno por IP externa
5. URL generada: `https://192.168.1.100:8000/download/file/abc123`
6. Frontend muestra ese enlace al usuario
7. Usuario hace click → **✅ DESCARGA FUNCIONA** (IP es accesible desde red)

## Configuración Paso a Paso

### Paso 1: Encontrar tu IP

**Windows:**
```powershell
ipconfig
# Busca "Adaptador de Ethernet" o "Adaptador de LAN inalámbrica"
# Dirección IPv4: 192.168.1.100  ← Esta es tu IP
```

**Linux/Mac:**
```bash
ifconfig  # o ip addr show
# Busca inet 192.168.1.100  ← Esta es tu IP
```

### Paso 2: Configurar Backend

Edita `backend/.env`:

```bash
# Reemplaza 192.168.1.100 con TU IP real
PUBLIC_URL=https://192.168.1.100:8000
EXTERNAL_IP=192.168.1.100
ENABLE_SSL=true
BACKEND_HOST=0.0.0.0  # Importante: 0.0.0.0 permite conexiones externas
```

### Paso 3: Configurar Frontend

Edita `frontend/.env`:

```bash
# Reemplaza 192.168.1.100 con TU IP real
DISTRISEARCH_BACKEND_URL=https://192.168.1.100:8000
DISTRISEARCH_BACKEND_PUBLIC_URL=https://192.168.1.100:8000
```

### Paso 4: Generar Certificados SSL (si usas HTTPS)

```powershell
cd DistriSearch\scripts
.\generate_ssl_certs.ps1 -Hostname "192.168.1.100"
```

### Paso 5: Configurar Firewall

```powershell
# Permitir puerto 8000 (Backend)
New-NetFirewallRule -DisplayName "DistriSearch Backend" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow

# Permitir puerto 8501 (Frontend)
New-NetFirewallRule -DisplayName "DistriSearch Frontend" -Direction Inbound -LocalPort 8501 -Protocol TCP -Action Allow
```

### Paso 6: Reiniciar Servicios

```powershell
# Backend
cd backend
python main.py

# Frontend
cd frontend
streamlit run app.py
```

## Verificación

### Desde la PC Servidor (192.168.1.100):

```powershell
# Verificar que el backend escucha en todas las interfaces
netstat -an | Select-String "8000"
# Debe mostrar: 0.0.0.0:8000 o [::]:8000
# NO debe mostrar: 127.0.0.1:8000
```

### Desde otra PC en la red (192.168.1.101):

```powershell
# Probar conectividad
Test-NetConnection -ComputerName 192.168.1.100 -Port 8000

# O con navegador
https://192.168.1.100:8000/health
# Debe responder: {"status":"healthy"}
```

### Prueba de Descarga:

1. Abre navegador en PC2 (192.168.1.101)
2. Ve a: `https://192.168.1.100:8501`
3. Busca un archivo
4. Inspecciona el botón de descarga (Click derecho → Inspeccionar)
5. Verifica que el enlace sea: `https://192.168.1.100:8000/download/file/...`
6. Click en Descargar
7. ✅ La descarga debe iniciar correctamente

## Casos de Uso Soportados

### Caso 1: Desarrollo Local (solo tu PC)
```bash
PUBLIC_URL=http://localhost:8000
ENABLE_SSL=false
```

### Caso 2: Red Local HTTP
```bash
PUBLIC_URL=http://192.168.1.100:8000
EXTERNAL_IP=192.168.1.100
ENABLE_SSL=false
```

### Caso 3: Red Local HTTPS (Recomendado)
```bash
PUBLIC_URL=https://192.168.1.100:8000
EXTERNAL_IP=192.168.1.100
ENABLE_SSL=true
SSL_CERT_FILE=../certs/distrisearch.crt
SSL_KEY_FILE=../certs/distrisearch.key
```

### Caso 4: Detrás de Reverse Proxy
```bash
PUBLIC_URL=https://distrisearch.tudominio.com
# El proxy debe enviar headers X-Forwarded-Host y X-Forwarded-Proto
```

### Caso 5: Docker Compose en Red
```bash
# En deploy/.env
EXTERNAL_IP=192.168.1.100
PUBLIC_URL=https://192.168.1.100:8000
DISTRISEARCH_BACKEND_PUBLIC_URL=https://192.168.1.100:8000
```

## Solución de Problemas

### ❌ Problema: Enlaces siguen mostrando localhost

**Causa:** Variables de entorno no configuradas o no cargadas

**Solución:**
```powershell
# Verificar configuración
cd backend
cat .env | Select-String "PUBLIC_URL"

# Debe mostrar algo como:
# PUBLIC_URL=https://192.168.1.100:8000

# Si está vacío o incorrecto, edítalo:
notepad .env

# Reinicia el backend
python main.py
```

### ❌ Problema: Enlaces muestran IP pero no descargan

**Causa 1:** Firewall bloqueando el puerto

**Solución:**
```powershell
# Verificar reglas del firewall
Get-NetFirewallRule -DisplayName "*DistriSearch*"

# Agregar regla si no existe
New-NetFirewallRule -DisplayName "DistriSearch Backend" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

**Causa 2:** Backend no escuchando en 0.0.0.0

**Solución:**
```bash
# En backend/.env
BACKEND_HOST=0.0.0.0  # NO usar 127.0.0.1 o localhost
```

### ❌ Problema: Certificado SSL inválido

**Causa:** Certificado autofirmado no confiado por el navegador

**Solución:**
```
Esto es NORMAL con certificados autofirmados.
En el navegador:
1. Click en "Avanzado"
2. Click en "Continuar al sitio" o "Aceptar riesgo"

Para eliminar la advertencia:
- Usa certificados de Let's Encrypt en producción
- O agrega el certificado a los certificados de confianza del sistema
```

### ❌ Problema: IP cambia frecuentemente (DHCP)

**Solución 1 - IP Estática:**
```
1. Accede a tu router
2. Configura una reserva DHCP para la MAC de tu PC
3. O configura IP estática en la configuración de red de Windows
```

**Solución 2 - Script de Actualización:**
```powershell
# update_ip.ps1
$newIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike "*Loopback*" }).IPAddress
$envFile = ".\backend\.env"
(Get-Content $envFile) -replace "PUBLIC_URL=https?://[\d\.]+:", "PUBLIC_URL=https://${newIP}:" | Set-Content $envFile
Write-Host "IP actualizada a: $newIP"
```

## Código Relevante

### Backend - `routes/download.py`

```python
def get_public_base_url(request: Request) -> str:
    """Obtiene URL pública del backend para red externa."""
    
    # 1. Variable de entorno (más confiable)
    public_url = os.getenv("PUBLIC_URL")
    if public_url:
        return public_url.rstrip('/')
    
    # 2. Headers de proxy
    forwarded_proto = request.headers.get("X-Forwarded-Proto", "http")
    forwarded_host = request.headers.get("X-Forwarded-Host")
    if forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}"
    
    # 3. Detección automática
    base_url = str(request.base_url).rstrip('/')
    parsed = urlparse(base_url)
    
    # Reemplazar hostnames internos
    if parsed.hostname in {"localhost", "127.0.0.1", "backend", "0.0.0.0"}:
        external_ip = os.getenv("EXTERNAL_IP") or detect_local_ip()
        protocol = "https" if os.getenv("ENABLE_SSL") == "true" else "http"
        port = parsed.port or (443 if protocol == "https" else 8000)
        
        return f"{protocol}://{external_ip}:{port}"
    
    return base_url

@router.post("/")
async def get_download_url(request: DownloadRequest, req: Request):
    """Genera URL de descarga con IP pública."""
    node, _ = _select_node_for_file(request.file_id)
    
    # Usar URL pública
    base = get_public_base_url(req)
    download_url = f"{base}/download/file/{request.file_id}"
    
    return {
        "download_url": download_url,
        "node": node
    }
```

## Impacto de los Cambios

### ✅ Beneficios:

1. **URLs accesibles en red:** Los enlaces funcionan desde cualquier PC
2. **Detección automática:** No requiere configuración manual (pero es recomendable)
3. **Soporte HTTPS:** URLs con protocolo correcto automáticamente
4. **Compatible con proxy:** Respeta headers X-Forwarded-*
5. **Fallback inteligente:** Si no hay config, detecta IP automáticamente

### ⚠️ Consideraciones:

1. **Certificados autofirmados:** El navegador mostrará advertencia (normal)
2. **IP dinámica:** Si la IP cambia (DHCP), hay que actualizar la configuración
3. **Firewall:** Debe permitir el tráfico entrante en los puertos configurados
4. **Red privada:** Las URLs solo funcionan dentro de la misma red local

## Testing

### Script de Prueba

```powershell
# test_network_access.ps1

$SERVER_IP = "192.168.1.100"
$BACKEND_PORT = 8000
$FRONTEND_PORT = 8501

Write-Host "=== Test de Acceso en Red ===" -ForegroundColor Cyan

# Test 1: Conectividad al backend
Write-Host "`n1. Probando conectividad al backend..." -ForegroundColor Yellow
Test-NetConnection -ComputerName $SERVER_IP -Port $BACKEND_PORT

# Test 2: Health check
Write-Host "`n2. Probando endpoint de health..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "https://$SERVER_IP:$BACKEND_PORT/health" -SkipCertificateCheck
    Write-Host "✅ Backend responde: $($response.Content)" -ForegroundColor Green
} catch {
    Write-Host "❌ Error: $_" -ForegroundColor Red
}

# Test 3: Frontend accesible
Write-Host "`n3. Probando acceso al frontend..." -ForegroundColor Yellow
Test-NetConnection -ComputerName $SERVER_IP -Port $FRONTEND_PORT

Write-Host "`n=== Pruebas completadas ===" -ForegroundColor Cyan
```

---

**Con esta solución, DistriSearch ahora funciona correctamente en redes locales y los enlaces de descarga son accesibles desde cualquier computadora en la red. 🎉**
