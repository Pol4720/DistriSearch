# DistriSearch - Script de inicio DHT
# Ejecutar desde la raíz del proyecto: .\DistriSearch\scripts\start_dht.ps1

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet('external', 'inproc')]
    [string]$Mode = 'external',
    
    [Parameter(Mandatory=$false)]
    [int]$DhtPort = 2000,
    
    [Parameter(Mandatory=$false)]
    [int]$BackendPort = 8000,
    
    [Parameter(Mandatory=$false)]
    [string]$SeedIP = '',
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipFrontend
)

Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║       DistriSearch - Inicio con DHT                       ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Verificar que estamos en la raíz del proyecto
if (-not (Test-Path ".\DistriSearch\backend\main.py")) {
    Write-Host "❌ Error: Ejecuta este script desde la raíz del proyecto (donde está la carpeta DistriSearch)" -ForegroundColor Red
    Write-Host "   Ejemplo: .\DistriSearch\scripts\start_dht.ps1" -ForegroundColor Yellow
    exit 1
}

Write-Host "📋 Configuración:" -ForegroundColor Green
Write-Host "   Modo DHT: $Mode" -ForegroundColor White
Write-Host "   Puerto DHT: $DhtPort" -ForegroundColor White
Write-Host "   Puerto Backend: $BackendPort" -ForegroundColor White
if ($SeedIP) {
    Write-Host "   Seed IP: $SeedIP" -ForegroundColor White
}
Write-Host ""

# Función para iniciar un proceso en una nueva ventana
function Start-ProcessInNewWindow {
    param($Title, $Command, $WorkingDirectory)
    
    Write-Host "🚀 Iniciando: $Title" -ForegroundColor Cyan
    
    $psCommand = "Write-Host '═══════════════════════════════════════' -ForegroundColor Cyan; " +
                 "Write-Host ' $Title' -ForegroundColor Green; " +
                 "Write-Host '═══════════════════════════════════════' -ForegroundColor Cyan; " +
                 "Write-Host ''; " +
                 "$Command; " +
                 "Write-Host ''; " +
                 "Write-Host 'Proceso finalizado. Presiona cualquier tecla para cerrar...' -ForegroundColor Yellow; " +
                 "[Console]::ReadKey() | Out-Null"
    
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $psCommand -WorkingDirectory $WorkingDirectory
}

# 1. Iniciar DHT si es modo external
if ($Mode -eq 'external') {
    Write-Host "📡 Iniciando servicio DHT externo..." -ForegroundColor Yellow
    Start-ProcessInNewWindow -Title "DHT Service (Flask)" -Command "python main.py" -WorkingDirectory ".\DHT"
    Start-Sleep -Seconds 3
}

# 2. Configurar y arrancar backend
Write-Host "⚙️  Configurando backend..." -ForegroundColor Yellow

$env:DHT_AUTO_START = "true"
$env:DHT_MODE = $Mode
$env:DHT_PORT = $DhtPort

if ($Mode -eq 'external') {
    $env:DHT_HTTP_URL = "http://127.0.0.1:8080"
}

if ($SeedIP) {
    $env:DHT_SEED_IP = $SeedIP
    $env:DHT_SEED_PORT = $DhtPort
}

$backendCommand = "`$env:DHT_AUTO_START='true'; " +
                  "`$env:DHT_MODE='$Mode'; " +
                  "`$env:DHT_PORT='$DhtPort'; "

if ($Mode -eq 'external') {
    $backendCommand += "`$env:DHT_HTTP_URL='http://127.0.0.1:8080'; "
}

if ($SeedIP) {
    $backendCommand += "`$env:DHT_SEED_IP='$SeedIP'; " +
                       "`$env:DHT_SEED_PORT='$DhtPort'; "
}

$backendCommand += "uvicorn main:app --reload --host 0.0.0.0 --port $BackendPort"

Start-ProcessInNewWindow -Title "Backend API" -Command $backendCommand -WorkingDirectory ".\DistriSearch\backend"
Start-Sleep -Seconds 5

# 3. Iniciar frontend
if (-not $SkipFrontend) {
    Write-Host "🎨 Iniciando frontend..." -ForegroundColor Yellow
    Start-ProcessInNewWindow -Title "Frontend (Streamlit)" -Command "streamlit run app.py" -WorkingDirectory ".\DistriSearch\frontend"
}

Write-Host ""
Write-Host "✅ Todos los servicios iniciados!" -ForegroundColor Green
Write-Host ""
Write-Host "📍 URLs de acceso:" -ForegroundColor Cyan
if ($Mode -eq 'external') {
    Write-Host "   DHT API:      http://localhost:8080" -ForegroundColor White
}
Write-Host "   Backend API:  http://localhost:$BackendPort" -ForegroundColor White
Write-Host "   Documentación: http://localhost:$BackendPort/docs" -ForegroundColor White
if (-not $SkipFrontend) {
    Write-Host "   Frontend:     http://localhost:8501" -ForegroundColor White
}
Write-Host ""
Write-Host "💡 Consejos:" -ForegroundColor Yellow
Write-Host "   • Usa Ctrl+C en cada ventana para detener los servicios" -ForegroundColor Gray
Write-Host "   • Revisa los logs en cada ventana para debug" -ForegroundColor Gray
Write-Host "   • Para unirte a una seed, usa la UI del frontend o la API" -ForegroundColor Gray
Write-Host ""
Write-Host "📚 Documentación completa: .\DistriSearch\DHT_INTEGRATION_GUIDE.md" -ForegroundColor Cyan
Write-Host ""

# Ejemplos de uso
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "Ejemplos de uso:" -ForegroundColor Magenta
Write-Host ""
Write-Host "# Modo external (DHT como servicio separado):" -ForegroundColor DarkGray
Write-Host ".\DistriSearch\scripts\start_dht.ps1 -Mode external" -ForegroundColor White
Write-Host ""
Write-Host "# Modo inproc (DHT dentro del backend):" -ForegroundColor DarkGray
Write-Host ".\DistriSearch\scripts\start_dht.ps1 -Mode inproc" -ForegroundColor White
Write-Host ""
Write-Host "# Conectar automáticamente a una seed:" -ForegroundColor DarkGray
Write-Host ".\DistriSearch\scripts\start_dht.ps1 -Mode inproc -SeedIP 192.168.1.10" -ForegroundColor White
Write-Host ""
Write-Host "# Sin frontend (solo backend + DHT):" -ForegroundColor DarkGray
Write-Host ".\DistriSearch\scripts\start_dht.ps1 -Mode inproc -SkipFrontend" -ForegroundColor White
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
