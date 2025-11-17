# 🚀 Comandos Rápidos - DistriSearch con DHT

## 📋 Inicio Rápido

### Opción 1: Script Automático (Más Fácil)

```powershell
# Desde la raíz del proyecto E:\Proyectos\DistriSearch

# Modo external (DHT separado)
.\DistriSearch\scripts\start_dht.ps1 -Mode external

# Modo inproc (DHT en backend)
.\DistriSearch\scripts\start_dht.ps1 -Mode inproc

# Con auto-join a seed
.\DistriSearch\scripts\start_dht.ps1 -Mode inproc -SeedIP 192.168.1.10
```

### Opción 2: Docker Compose

```powershell
cd DistriSearch\deploy
docker-compose up -d --build
docker-compose logs -f
```

### Opción 3: Manual

```powershell
# Terminal 1 - DHT (si usas external)
cd DHT
python main.py

# Terminal 2 - Backend
cd DistriSearch\backend
$env:DHT_AUTO_START="true"; $env:DHT_MODE="external"; uvicorn main:app --reload

# Terminal 3 - Frontend
cd DistriSearch\frontend
streamlit run app.py
```

---

## 🔍 Verificación

```powershell
# Health backend
Invoke-RestMethod http://localhost:8000/health

# Estado DHT desde backend
Invoke-RestMethod http://localhost:8000/dht/sucpred

# DHT directa (modo external)
Invoke-RestMethod http://localhost:8080/server/rest/DHT/imprimirSucPred

# Frontend
Start-Process "http://localhost:8501"
```

---

## 🎮 Operaciones DHT desde PowerShell

### Iniciar DHT

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/dht/start"
```

### Unirse a Red

```powershell
$params = @{seed_ip="192.168.1.10"; seed_port=2000}
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/dht/join" -Body $params
```

### Subir Archivo

```powershell
$params = @{filename="test.txt"; data="Contenido de prueba"}
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/dht/upload" -Body $params
```

### Descargar Archivo

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/dht/download?filename=test.txt"
```

### Ver Finger Table

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/dht/finger"
```

### Ver Sucesor/Predecesor

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/dht/sucpred"
```

---

## 🐳 Docker

```powershell
# Iniciar
cd DistriSearch\deploy
docker-compose up -d

# Ver logs
docker-compose logs -f dht
docker-compose logs -f backend

# Reiniciar servicio
docker-compose restart dht

# Detener
docker-compose down

# Limpiar todo
docker-compose down -v
```

---

## 🔧 Configuración Rápida

### Variables de Entorno - Modo External

```powershell
$env:DHT_AUTO_START = "true"
$env:DHT_MODE = "external"
$env:DHT_HTTP_URL = "http://127.0.0.1:8080"
```

### Variables de Entorno - Modo Inproc

```powershell
$env:DHT_AUTO_START = "true"
$env:DHT_MODE = "inproc"
$env:DHT_PORT = "2000"
```

### Con Auto-Join a Seed

```powershell
$env:DHT_SEED_IP = "192.168.1.10"
$env:DHT_SEED_PORT = "2000"
```

---

## 📊 Monitoreo

```powershell
# Ver procesos Python
Get-Process python

# Ver puertos en uso
netstat -ano | findstr ":8000"
netstat -ano | findstr ":8080"
netstat -ano | findstr ":2000"
netstat -ano | findstr ":8501"

# Matar proceso por puerto
$port = 8000
$pid = (Get-NetTCPConnection -LocalPort $port).OwningProcess
Stop-Process -Id $pid -Force
```

---

## 🐛 Troubleshooting

### Puerto Ocupado

```powershell
# Ver qué usa el puerto
netstat -ano | findstr :2000

# Matar proceso
taskkill /PID <PID> /F
```

### Reiniciar Todo

```powershell
# Matar todos los procesos Python
Get-Process python | Stop-Process -Force

# Limpiar y reiniciar
.\DistriSearch\scripts\start_dht.ps1 -Mode inproc
```

### Ver Logs Detallados

```powershell
# Backend con logs verbose
cd DistriSearch\backend
$env:LOG_LEVEL="DEBUG"
uvicorn main:app --reload --log-level debug

# DHT con logs
cd DHT
$env:FLASK_DEBUG="1"
python main.py
```

---

## 🌐 Acceso Red Externa

### Configurar Firewall

```powershell
# Permitir puertos
New-NetFirewallRule -DisplayName "DistriSearch Backend" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "DistriSearch DHT HTTP" -Direction Inbound -LocalPort 8080 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "DistriSearch DHT P2P" -Direction Inbound -LocalPort 2000 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "DistriSearch Frontend" -Direction Inbound -LocalPort 8501 -Protocol TCP -Action Allow
```

### Obtener IP Local

```powershell
# Opción 1
ipconfig | findstr IPv4

# Opción 2
(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -like "192.168.*"}).IPAddress

# Opción 3
[System.Net.Dns]::GetHostAddresses([System.Net.Dns]::GetHostName()) | Where-Object {$_.AddressFamily -eq "InterNetwork"}
```

---

## 📦 Instalación Dependencias

```powershell
# Backend
cd DistriSearch\backend
pip install -r requirements.txt

# Frontend
cd DistriSearch\frontend
pip install -r requirements.txt

# DHT
cd DHT
pip install -r requirements.txt
```

---

## 🧪 Testing

```powershell
# Test básico
cd DistriSearch\backend
pytest tests/

# Test específico
pytest tests/test_dht.py -v

# Con coverage
pytest --cov=services --cov=routes tests/
```

---

## 📚 URLs de Referencia

- Backend API: http://localhost:8000
- Documentación: http://localhost:8000/docs
- DHT API: http://localhost:8080
- Frontend: http://localhost:8501

---

## ✅ Checklist Diario

```powershell
# 1. Verificar servicios
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8080/server/rest/DHT/imprimirSucPred

# 2. Ver estado DHT
Invoke-RestMethod http://localhost:8000/dht/sucpred

# 3. Abrir frontend
Start-Process "http://localhost:8501"

# 4. Ver logs si hay problemas
docker-compose logs -f  # Si usas Docker
# O revisar terminal del backend/DHT
```

---

## 🎯 Comandos según Escenario

### Desarrollo Local (1 máquina)

```powershell
.\DistriSearch\scripts\start_dht.ps1 -Mode inproc
```

### Testing Multi-Nodo (1 máquina, puertos diferentes)

```powershell
# Nodo 1 (seed)
cd DistriSearch\backend
$env:DHT_AUTO_START="true"; $env:DHT_MODE="inproc"; $env:DHT_PORT="2000"
uvicorn main:app --reload --port 8000

# Nodo 2
cd DistriSearch\backend
$env:DHT_AUTO_START="true"; $env:DHT_MODE="inproc"; $env:DHT_PORT="2001"
$env:DHT_SEED_IP="127.0.0.1"; $env:DHT_SEED_PORT="2000"
uvicorn main:app --reload --port 8001
```

### Producción (Docker)

```powershell
cd DistriSearch\deploy
docker-compose up -d --build
docker-compose logs -f
```

---

*Referencia rápida - Guarda este archivo para acceso inmediato a comandos comunes*
