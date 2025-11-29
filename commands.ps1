# DistriSearch - Scripts de Utilidad PowerShell
# Ejecutar: .\commands.ps1 <comando>

param(
    [Parameter(Position=0)]
    [string]$Command = "help"
)

function Show-Help {
    Write-Host @"

╔══════════════════════════════════════════════════════════════╗
║         DistriSearch - Comandos Disponibles                 ║
╚══════════════════════════════════════════════════════════════╝

DESARROLLO:
  install         Instala dependencias
  demo            Ejecuta demo rápida
  interactive     Modo interactivo (5 nodos)
  test            Ejecuta todos los tests
  test-verbose    Tests con salida detallada

DOCKER:
  docker-build    Construye imagen Docker
  docker-up       Inicia contenedores (3 nodos)
  docker-down     Detiene contenedores
  docker-logs     Muestra logs de contenedores

LIMPIEZA:
  clean           Limpia archivos temporales
  clean-data      Limpia datos persistentes
  clean-all       Limpieza completa

EJEMPLOS:
  .\commands.ps1 demo
  .\commands.ps1 test
  .\commands.ps1 docker-up

"@
}

function Install-Dependencies {
    Write-Host "📦 Instalando dependencias..." -ForegroundColor Green
    pip install -r requirements.txt
}

function Run-Demo {
    Write-Host "🚀 Ejecutando demo..." -ForegroundColor Green
    python demo.py
}

function Run-Interactive {
    Write-Host "🎮 Iniciando modo interactivo..." -ForegroundColor Green
    python simulator.py --nodes 5
}

function Run-Tests {
    Write-Host "🧪 Ejecutando tests..." -ForegroundColor Green
    python run_tests.py
}

function Run-TestsVerbose {
    Write-Host "🧪 Ejecutando tests (verbose)..." -ForegroundColor Green
    pytest -v
}

function Build-Docker {
    Write-Host "🐳 Construyendo imagen Docker..." -ForegroundColor Green
    docker build -t distrisearch .
}

function Start-Docker {
    Write-Host "🐳 Iniciando contenedores..." -ForegroundColor Green
    docker-compose up
}

function Stop-Docker {
    Write-Host "🐳 Deteniendo contenedores..." -ForegroundColor Green
    docker-compose down
}

function Show-DockerLogs {
    Write-Host "📋 Mostrando logs..." -ForegroundColor Green
    docker-compose logs -f
}

function Clean-Temp {
    Write-Host "🧹 Limpiando archivos temporales..." -ForegroundColor Yellow
    
    if (Test-Path "__pycache__") { Remove-Item -Recurse -Force "__pycache__" }
    if (Test-Path ".pytest_cache") { Remove-Item -Recurse -Force ".pytest_cache" }
    if (Test-Path "htmlcov") { Remove-Item -Recurse -Force "htmlcov" }
    if (Test-Path ".coverage") { Remove-Item -Force ".coverage" }
    if (Test-Path "*.log") { Remove-Item -Force "*.log" }
    
    Get-ChildItem -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
    
    Write-Host "✓ Limpieza completada" -ForegroundColor Green
}

function Clean-Data {
    Write-Host "🧹 Limpiando datos persistentes..." -ForegroundColor Yellow
    
    if (Test-Path "data") { Remove-Item -Recurse -Force "data" }
    
    Write-Host "✓ Datos eliminados" -ForegroundColor Green
}

function Clean-All {
    Write-Host "🧹 Limpieza completa..." -ForegroundColor Yellow
    
    Clean-Temp
    Clean-Data
    
    Write-Host "✓ Limpieza completa terminada" -ForegroundColor Green
}

# Ejecutar comando
switch ($Command.ToLower()) {
    "help" { Show-Help }
    "install" { Install-Dependencies }
    "demo" { Run-Demo }
    "interactive" { Run-Interactive }
    "test" { Run-Tests }
    "test-verbose" { Run-TestsVerbose }
    "docker-build" { Build-Docker }
    "docker-up" { Start-Docker }
    "docker-down" { Stop-Docker }
    "docker-logs" { Show-DockerLogs }
    "clean" { Clean-Temp }
    "clean-data" { Clean-Data }
    "clean-all" { Clean-All }
    default {
        Write-Host "❌ Comando desconocido: $Command" -ForegroundColor Red
        Write-Host ""
        Show-Help
    }
}
