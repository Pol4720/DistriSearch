# 🚀 Guía de Inicio Rápido - DistriSearch con HTTPS

Esta guía te ayudará a configurar DistriSearch con HTTPS para acceso en red local en **menos de 10 minutos**.

## ⚡ Inicio Rápido

### 1️⃣ Obtener tu IP Local

```powershell
# Windows
ipconfig
# Busca tu IP (ejemplo: 192.168.1.100)
```

### 2️⃣ Generar Certificados SSL

```powershell
cd DistriSearch\scripts
.\generate_ssl_certs.ps1 -Hostname "192.168.1.100"  # Reemplaza con tu IP
```

### 3️⃣ Configurar Backend

```powershell
cd ..\backend
cp .env.example .env
notepad .env
```

**Edita estas líneas** (reemplaza `192.168.1.100` con tu IP real):

```bash
PUBLIC_URL=https://192.168.1.100:8000
EXTERNAL_IP=192.168.1.100
ENABLE_SSL=true
SSL_CERT_FILE=../certs/distrisearch.crt
SSL_KEY_FILE=../certs/distrisearch.key
BACKEND_HOST=0.0.0.0
```

### 4️⃣ Configurar Frontend

```powershell
cd ..\frontend
cp .env.example .env
notepad .env
```

**Edita estas líneas**:

```bash
DISTRISEARCH_BACKEND_URL=https://192.168.1.100:8000
DISTRISEARCH_BACKEND_PUBLIC_URL=https://192.168.1.100:8000
```

### 5️⃣ Abrir Firewall

```powershell
# Ejecuta como Administrador
New-NetFirewallRule -DisplayName "DistriSearch Backend" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "DistriSearch Frontend" -Direction Inbound -LocalPort 8501 -Protocol TCP -Action Allow
```

### 6️⃣ Iniciar Servicios

**Terminal 1 - Backend:**
```powershell
cd DistriSearch\backend
pip install -r requirements.txt
python main.py
```

**Terminal 2 - Frontend:**
```powershell
cd DistriSearch\frontend
pip install -r requirements.txt
streamlit run app.py
```

### 7️⃣ Acceder desde otra PC

En cualquier computadora de tu red:

1. Abre el navegador
2. Ve a: `https://192.168.1.100:8501` (usa tu IP)
3. Acepta la advertencia del certificado (es normal con certificados autofirmados)
4. ¡Listo! Busca archivos y descárgalos

## ✅ Verificación Rápida

### En el servidor:
```powershell
# Verificar que escucha en todas las interfaces
netstat -an | Select-String "8000"
# Debe mostrar: 0.0.0.0:8000
```

### En otra PC:
```powershell
# Probar conectividad
Test-NetConnection -ComputerName 192.168.1.100 -Port 8000

# Probar con navegador
https://192.168.1.100:8000/health
# Debe responder: {"status":"healthy"}
```

## 🐳 Con Docker (Alternativa)

### Configuración Rápida

```powershell
cd DistriSearch\deploy
cp .env.example .env
notepad .env
```

**Edita** (reemplaza con tu IP):

```bash
EXTERNAL_IP=192.168.1.100
PUBLIC_URL=https://192.168.1.100:8000
DISTRISEARCH_BACKEND_PUBLIC_URL=https://192.168.1.100:8000
ENABLE_SSL=true
AGENT_SSL_ENABLED=true
```

### Iniciar

```powershell
# Generar certificados primero
cd ..\scripts
.\generate_ssl_certs.ps1 -Hostname "192.168.1.100"

# Iniciar con Docker
cd ..\deploy
docker-compose up -d --build

# Ver logs
docker-compose logs -f
```

**Acceso:**
- Frontend: `http://192.168.1.100:8501`
- Backend: `https://192.168.1.100:8000`
- API Docs: `https://192.168.1.100:8000/docs`

## 🔍 Solución de Problemas Comunes

### ❌ Enlaces de descarga muestran "localhost"

**Solución:** Verifica que `PUBLIC_URL` y `EXTERNAL_IP` están configuradas correctamente en `backend/.env`

```powershell
cd backend
cat .env | Select-String "PUBLIC_URL"
# Debe mostrar: PUBLIC_URL=https://192.168.1.100:8000
```

Si no, edítalo y reinicia el backend.

### ❌ No puedo conectarme desde otra PC

**Solución:** Verifica el firewall

```powershell
# Ver reglas
Get-NetFirewallRule -DisplayName "*DistriSearch*"

# Agregar si no existe
New-NetFirewallRule -DisplayName "DistriSearch" -Direction Inbound -LocalPort 8000,8501 -Protocol TCP -Action Allow
```

### ❌ "Tu conexión no es privada" en el navegador

**Esto es normal** con certificados autofirmados. 

**Solución:** Click en "Avanzado" → "Continuar al sitio"

Para producción, usa certificados de Let's Encrypt.

### ❌ "Address already in use"

**Solución:** Mata el proceso que usa el puerto

```powershell
# Encontrar proceso
netstat -ano | Select-String ":8000"

# Matar proceso (reemplaza 1234 con el PID real)
taskkill /PID 1234 /F
```

## 📚 Documentación Completa

Para más detalles, consulta:

- **[Guía Completa HTTPS](./HTTPS_SETUP.md)** - Configuración detallada de SSL/TLS
- **[Solución URLs de Descarga](./NETWORK_DOWNLOAD_FIX.md)** - Detalles técnicos de la solución

## 🎯 Resumen de Archivos de Configuración

### Estructura de Archivos

```
DistriSearch/
├── certs/                          ← Certificados SSL aquí
│   ├── distrisearch.crt
│   ├── distrisearch.key
│   └── distrisearch.pem
├── backend/
│   └── .env                        ← Configuración del backend
├── frontend/
│   └── .env                        ← Configuración del frontend
├── agent/
│   └── .env                        ← Configuración de agentes
└── deploy/
    └── .env                        ← Configuración de Docker
```

### Variables Clave

| Variable | Ubicación | Ejemplo | Descripción |
|----------|-----------|---------|-------------|
| `PUBLIC_URL` | backend/.env | `https://192.168.1.100:8000` | URL pública del backend |
| `EXTERNAL_IP` | backend/.env | `192.168.1.100` | IP de tu máquina |
| `ENABLE_SSL` | backend/.env | `true` | Habilitar HTTPS |
| `BACKEND_HOST` | backend/.env | `0.0.0.0` | Escuchar en todas las interfaces |
| `DISTRISEARCH_BACKEND_URL` | frontend/.env | `https://192.168.1.100:8000` | URL del backend |
| `DISTRISEARCH_BACKEND_PUBLIC_URL` | frontend/.env | `https://192.168.1.100:8000` | URL para descargas |

## 📋 Checklist

- [ ] Obtener IP local con `ipconfig`
- [ ] Generar certificados con `generate_ssl_certs.ps1`
- [ ] Configurar `backend/.env` con tu IP
- [ ] Configurar `frontend/.env` con tu IP
- [ ] Abrir puertos en el firewall (8000, 8501)
- [ ] Iniciar backend y frontend
- [ ] Probar desde otra PC: `https://TU_IP:8501`
- [ ] Verificar que los enlaces de descarga usan tu IP (no localhost)

## 🎉 ¡Listo!

Ahora tienes:

- ✅ **HTTPS** habilitado (comunicación segura)
- ✅ **Acceso desde red** (cualquier PC puede acceder)
- ✅ **Enlaces de descarga funcionales** (no más localhost)
- ✅ **Configuración persistente** (variables de entorno)

---

**¿Necesitas ayuda?** Revisa la [documentación completa](./HTTPS_SETUP.md) o abre un issue en el repositorio.
