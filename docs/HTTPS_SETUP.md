# 🔒 Guía de Configuración HTTPS y Acceso en Red

Esta guía explica cómo configurar DistriSearch con **HTTPS** (SSL/TLS) y habilitar el acceso desde otras computadoras en la red local.

## 📋 Tabla de Contenidos

1. [Requisitos Previos](#requisitos-previos)
2. [Generar Certificados SSL](#generar-certificados-ssl)
3. [Configuración del Backend](#configuración-del-backend)
4. [Configuración de Agentes](#configuración-de-agentes)
5. [Configuración del Frontend](#configuración-del-frontend)
6. [Configuración con Docker](#configuración-con-docker)
7. [Acceso desde Red Externa](#acceso-desde-red-externa)
8. [Solución de Problemas](#solución-de-problemas)
9. [Certificados en Producción](#certificados-en-producción)

---

## 🔧 Requisitos Previos

### Software Necesario

- **Python 3.8+** instalado
- **OpenSSL** (incluido con Git for Windows o instalable vía Chocolatey)
- **PowerShell** 5.1 o superior

### Verificar Instalaciones

```powershell
# Verificar Python
python --version

# Verificar OpenSSL
openssl version

# Si OpenSSL no está instalado, usa Chocolatey:
choco install openssl -y
```

---

## 🔐 Generar Certificados SSL

### Paso 1: Ejecutar el Script de Generación

DistriSearch incluye un script PowerShell para generar certificados autofirmados:

```powershell
# Navegar al directorio de scripts
cd DistriSearch\scripts

# Obtener tu IP local
ipconfig

# Ejecutar el script con tu IP (reemplaza 192.168.1.100 con tu IP real)
.\generate_ssl_certs.ps1 -Hostname "192.168.1.100"
```

### Paso 2: Verificar Certificados Generados

El script creará los siguientes archivos en `DistriSearch/certs/`:

- `distrisearch.crt` - Certificado público
- `distrisearch.key` - Clave privada
- `distrisearch.pem` - Certificado combinado
- `openssl.cnf` - Configuración de OpenSSL

```powershell
# Verificar que los archivos existen
ls ..\certs\
```

### Ubicación de Certificados

```
DistriSearch/
├── certs/                          ← Certificados aquí
│   ├── distrisearch.crt
│   ├── distrisearch.key
│   └── distrisearch.pem
├── backend/
├── agent/
└── frontend/
```

---

## ⚙️ Configuración del Backend

### Paso 1: Crear Archivo .env

```powershell
# Navegar al directorio del backend
cd ..\backend

# Copiar el archivo de ejemplo
cp .env.example .env
```

### Paso 2: Editar Configuración

Abre `.env` y configura:

```bash
# =============================================================================
# CONFIGURACIÓN PARA RED LOCAL CON HTTPS
# =============================================================================

# IMPORTANTE: Reemplaza 192.168.1.100 con tu IP real
PUBLIC_URL=https://192.168.1.100:8000
EXTERNAL_IP=192.168.1.100

# Habilitar SSL/TLS
ENABLE_SSL=true
SSL_CERT_FILE=../certs/distrisearch.crt
SSL_KEY_FILE=../certs/distrisearch.key

# Configuración del servidor
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000

# Opcional: API Key para seguridad adicional
ADMIN_API_KEY=tu_clave_secreta_aqui
```

### Paso 3: Iniciar el Backend

```powershell
# Instalar dependencias (si no lo has hecho)
pip install -r requirements.txt

# Iniciar el backend
python main.py
```

Deberías ver:

```
============================================================
DistriSearch Backend Iniciando
============================================================
Protocolo: HTTPS
Host: 0.0.0.0
Puerto: 8000
IP Local (LAN): 192.168.1.100
SSL Habilitado: ✓
Certificado: ../certs/distrisearch.crt
Clave privada: ../certs/distrisearch.key
------------------------------------------------------------
Acceso Local: https://localhost:8000
Acceso Red (LAN): https://192.168.1.100:8000
Documentación: https://localhost:8000/docs
============================================================
```

---

## 🤖 Configuración de Agentes

### Paso 1: Crear Archivo .env

```powershell
cd ..\agent
cp .env.example .env
```

### Paso 2: Editar Configuración

```bash
# Backend URL (usa HTTPS si el backend lo tiene habilitado)
BACKEND_URL=https://192.168.1.100:8000

# Configuración del agente
NODE_NAME=Agent-1
FILE_SERVER_PORT=5001
SHARED_FOLDER=./shared_folder

# Habilitar SSL en el servidor del agente
AGENT_SSL_ENABLED=true
AGENT_SSL_CERT_FILE=../certs/distrisearch.crt
AGENT_SSL_KEY_FILE=../certs/distrisearch.key

# NO verificar certificados autofirmados
VERIFY_SSL=false
```

### Paso 3: Iniciar el Agente

```powershell
# Instalar dependencias
pip install -r requirements.txt

# Iniciar el agente
python agent.py
```

---

## 🖥️ Configuración del Frontend

### Paso 1: Crear Archivo .env

```powershell
cd ..\frontend
cp .env.example .env
```

### Paso 2: Editar Configuración

```bash
# URL del backend (HTTPS con tu IP)
DISTRISEARCH_BACKEND_URL=https://192.168.1.100:8000

# URL pública para enlaces de descarga (mismo valor)
DISTRISEARCH_BACKEND_PUBLIC_URL=https://192.168.1.100:8000

# API Key (si configuraste ADMIN_API_KEY en el backend)
DISTRISEARCH_ADMIN_API_KEY=tu_clave_secreta_aqui
```

### Paso 3: Iniciar el Frontend

```powershell
# Instalar dependencias
pip install -r requirements.txt

# Iniciar Streamlit
streamlit run app.py
```

---

## 🐳 Configuración con Docker

### Paso 1: Preparar Certificados

```powershell
# Asegurarse de que los certificados existen
cd DistriSearch
mkdir -p certs
cd scripts
.\generate_ssl_certs.ps1 -Hostname "192.168.1.100"
```

### Paso 2: Configurar Variables de Entorno

```powershell
cd ..\deploy
cp .env.example .env
```

Editar `deploy/.env`:

```bash
# Tu IP de red (reemplaza con tu IP real)
EXTERNAL_IP=192.168.1.100

# URLs públicas con HTTPS
PUBLIC_URL=https://192.168.1.100:8000
DISTRISEARCH_BACKEND_PUBLIC_URL=https://192.168.1.100:8000

# Habilitar SSL
ENABLE_SSL=true
AGENT_SSL_ENABLED=true
VERIFY_SSL=false

# Opcional: Seguridad adicional
ADMIN_API_KEY=tu_clave_secreta
```

### Paso 3: Iniciar con Docker Compose

```powershell
# Construir e iniciar todos los servicios
docker-compose up -d --build

# Ver logs
docker-compose logs -f backend

# Verificar estado
docker-compose ps
```

### Acceso

- **Backend:** https://192.168.1.100:8000
- **Frontend:** http://192.168.1.100:8501
- **Documentación API:** https://192.168.1.100:8000/docs

---

## 🌐 Acceso desde Red Externa

### Permitir Conexiones en el Firewall

#### Windows Firewall

```powershell
# Permitir puerto 8000 (Backend HTTPS)
New-NetFirewallRule -DisplayName "DistriSearch Backend HTTPS" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow

# Permitir puerto 8501 (Frontend)
New-NetFirewallRule -DisplayName "DistriSearch Frontend" -Direction Inbound -LocalPort 8501 -Protocol TCP -Action Allow

# Si usas agentes, permitir sus puertos también
New-NetFirewallRule -DisplayName "DistriSearch Agent 1" -Direction Inbound -LocalPort 5001 -Protocol TCP -Action Allow
```

### Verificar Conectividad

Desde otra computadora en la red:

```powershell
# Probar conectividad
Test-NetConnection -ComputerName 192.168.1.100 -Port 8000

# O con curl/Invoke-WebRequest
Invoke-WebRequest -Uri "https://192.168.1.100:8000/health" -SkipCertificateCheck
```

### Acceso desde Navegador

1. Abre tu navegador en **otra computadora**
2. Ve a: `https://192.168.1.100:8501`
3. **Importante:** Acepta la advertencia de certificado autofirmado
   - Chrome/Edge: Click en "Avanzado" → "Continuar a 192.168.1.100"
   - Firefox: Click en "Avanzado" → "Aceptar el riesgo y continuar"

---

## 🔍 Solución de Problemas

### Problema: Certificado no válido

**Síntoma:** El navegador muestra "Tu conexión no es privada"

**Solución:**
- Esto es **normal** con certificados autofirmados
- Acepta la advertencia o agrega el certificado a los certificados de confianza del sistema

### Problema: Enlaces de descarga muestran localhost

**Síntoma:** Los botones de descarga muestran `http://localhost:8000/...`

**Solución:**
1. Verifica que `PUBLIC_URL` y `EXTERNAL_IP` están configuradas en el backend
2. Verifica que `DISTRISEARCH_BACKEND_PUBLIC_URL` está configurada en el frontend
3. Reinicia el backend y el frontend

```powershell
# Verificar configuración del backend
cd DistriSearch\backend
cat .env | Select-String "PUBLIC_URL"

# Debe mostrar algo como:
# PUBLIC_URL=https://192.168.1.100:8000
```

### Problema: No se puede conectar desde otra PC

**Síntomas posibles:**
- "No se puede establecer conexión"
- Timeout al acceder

**Soluciones:**

1. **Verificar Firewall:**
   ```powershell
   # Ver reglas del firewall
   Get-NetFirewallRule -DisplayName "*DistriSearch*"
   ```

2. **Verificar que el servicio escucha en 0.0.0.0:**
   ```powershell
   # Ver puertos en uso
   netstat -an | Select-String "8000"
   ```
   Debe mostrar `0.0.0.0:8000` no `127.0.0.1:8000`

3. **Verificar IP correcta:**
   ```powershell
   ipconfig
   ```
   Busca tu adaptador de red principal (no virtual ni VPN)

### Problema: SSL Certificate Verify Failed

**Síntoma:** Error al conectar agentes con backend HTTPS

**Solución:**
```bash
# En agent/.env
VERIFY_SSL=false
```

Para agentes en Python, también puedes:
```python
# Deshabilitar advertencias de SSL
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
```

### Problema: Puerto ya en uso

**Síntoma:** `Address already in use`

**Solución:**
```powershell
# Encontrar proceso usando el puerto 8000
netstat -ano | Select-String ":8000"

# Matar el proceso (reemplaza PID con el número de la columna final)
taskkill /PID <PID> /F
```

---

## 🏆 Certificados en Producción

Para **entornos de producción**, **NO uses certificados autofirmados**. Usa certificados válidos:

### Opción 1: Let's Encrypt (Gratis)

```bash
# Instalar certbot
choco install certbot -y

# Obtener certificado (requiere dominio público)
certbot certonly --standalone -d tudominio.com
```

Los certificados estarán en:
- `/etc/letsencrypt/live/tudominio.com/fullchain.pem`
- `/etc/letsencrypt/live/tudominio.com/privkey.pem`

Actualiza en `.env`:
```bash
SSL_CERT_FILE=/etc/letsencrypt/live/tudominio.com/fullchain.pem
SSL_KEY_FILE=/etc/letsencrypt/live/tudominio.com/privkey.pem
```

### Opción 2: Certificado Comercial

Compra un certificado de una CA (Certificate Authority) confiable:
- DigiCert
- GlobalSign
- Sectigo

---

## 📝 Checklist de Configuración

### Para HTTP (Desarrollo Local)

- [ ] Backend: `ENABLE_SSL=false`
- [ ] Backend: `PUBLIC_URL=http://localhost:8000`
- [ ] Frontend: `DISTRISEARCH_BACKEND_URL=http://localhost:8000`

### Para HTTPS (Red Local)

- [ ] Generar certificados: `.\scripts\generate_ssl_certs.ps1`
- [ ] Obtener IP local: `ipconfig`
- [ ] Backend: `ENABLE_SSL=true`
- [ ] Backend: `PUBLIC_URL=https://TU_IP:8000`
- [ ] Backend: `EXTERNAL_IP=TU_IP`
- [ ] Agentes: `AGENT_SSL_ENABLED=true`
- [ ] Agentes: `VERIFY_SSL=false`
- [ ] Frontend: `DISTRISEARCH_BACKEND_URL=https://TU_IP:8000`
- [ ] Frontend: `DISTRISEARCH_BACKEND_PUBLIC_URL=https://TU_IP:8000`
- [ ] Firewall: Permitir puertos 8000, 8501
- [ ] Probar desde otra PC

---

## 🎯 Ejemplo Completo de Configuración

### Escenario: 2 PCs en red local

**PC1 (Servidor):** IP `192.168.1.100`
**PC2 (Cliente):** IP `192.168.1.101`

### En PC1 (Servidor):

1. **Generar certificados:**
   ```powershell
   cd DistriSearch\scripts
   .\generate_ssl_certs.ps1 -Hostname "192.168.1.100"
   ```

2. **Configurar backend** (`backend/.env`):
   ```bash
   PUBLIC_URL=https://192.168.1.100:8000
   EXTERNAL_IP=192.168.1.100
   ENABLE_SSL=true
   SSL_CERT_FILE=../certs/distrisearch.crt
   SSL_KEY_FILE=../certs/distrisearch.key
   BACKEND_HOST=0.0.0.0
   BACKEND_PORT=8000
   ```

3. **Configurar frontend** (`frontend/.env`):
   ```bash
   DISTRISEARCH_BACKEND_URL=https://192.168.1.100:8000
   DISTRISEARCH_BACKEND_PUBLIC_URL=https://192.168.1.100:8000
   ```

4. **Abrir firewall:**
   ```powershell
   New-NetFirewallRule -DisplayName "DistriSearch" -Direction Inbound -LocalPort 8000,8501 -Protocol TCP -Action Allow
   ```

5. **Iniciar servicios:**
   ```powershell
   # Terminal 1: Backend
   cd backend
   python main.py

   # Terminal 2: Frontend
   cd frontend
   streamlit run app.py
   ```

### En PC2 (Cliente):

1. Abre el navegador
2. Ve a: `https://192.168.1.100:8501`
3. Acepta la advertencia del certificado autofirmado
4. ¡Usa DistriSearch! Los enlaces de descarga funcionarán correctamente

---

## 📚 Referencias Adicionales

- [FastAPI SSL/TLS Documentation](https://fastapi.tiangolo.com/deployment/https/)
- [Uvicorn SSL Configuration](https://www.uvicorn.org/#running-with-https)
- [OpenSSL Documentation](https://www.openssl.org/docs/)
- [Let's Encrypt](https://letsencrypt.org/)

---

## 🆘 Soporte

Si encuentras problemas:

1. Revisa los logs del backend: `backend/logs/`
2. Verifica la configuración de red: `ipconfig` / `ifconfig`
3. Prueba la conectividad: `Test-NetConnection`
4. Revisa el firewall: `Get-NetFirewallRule`

Para más ayuda, abre un issue en el repositorio del proyecto.

---

**¡Ahora tu DistriSearch está seguro con HTTPS y accesible desde toda tu red! 🔒✨**
