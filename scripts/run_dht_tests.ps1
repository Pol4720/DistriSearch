# Script para ejecutar todos los tests DHT
# Uso: .\run_dht_tests.ps1 [correctness|robustness|unit|integration|e2e|all|smoke]

param(
    [Parameter(Position=0)]
    [ValidateSet("correctness", "robustness", "unit", "integration", "e2e", "all", "smoke", "")]
    [string]$TestSuite = "smoke"
)

# Colores
function Write-Success { Write-Host $args -ForegroundColor Green }
function Write-Error-Custom { Write-Host $args -ForegroundColor Red }
function Write-Info { Write-Host $args -ForegroundColor Cyan }
function Write-Warning-Custom { Write-Host $args -ForegroundColor Yellow }

# Banner
Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║          🧪 Suite de Tests DHT - DistriSearch            ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Verificar ubicación
$projectRoot = "E:\Proyectos\DistriSearch"
if (-not (Test-Path $projectRoot)) {
    Write-Error-Custom "❌ No se encuentra el proyecto en $projectRoot"
    exit 1
}

Set-Location $projectRoot

# Verificar dependencias
Write-Info "🔍 Verificando dependencias..."

$pythonVersion = python --version 2>&1
Write-Host "   Python: $pythonVersion"

$pipPackages = @("pytest", "pytest-cov", "pytest-asyncio")
foreach ($package in $pipPackages) {
    $installed = pip show $package 2>$null
    if ($installed) {
        Write-Success "   ✅ $package instalado"
    } else {
        Write-Warning-Custom "   ⚠️  $package NO instalado"
        Write-Info "   Instalando $package..."
        pip install $package -q
    }
}

# Verificar módulo DHT
Write-Info "`n🔍 Verificando módulo DHT..."
$dhtCheck = python -c "from DHT.peer import Peer; print('OK')" 2>&1
if ($dhtCheck -like "*OK*") {
    Write-Success "   ✅ Módulo DHT disponible"
} else {
    Write-Error-Custom "   ❌ Módulo DHT no disponible"
    Write-Info "   Ajustando PYTHONPATH..."
    $env:PYTHONPATH = "$projectRoot;$env:PYTHONPATH"
}

Write-Host ""

# Contadores
$totalTests = 0
$passedTests = 0
$failedTests = 0
$startTime = Get-Date

# Función para ejecutar tests
function Run-Tests {
    param($Name, $Command, $WorkDir)
    
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray
    Write-Info "📋 Ejecutando: $Name"
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray
    
    $prevLocation = Get-Location
    if ($WorkDir) {
        Set-Location $WorkDir
    }
    
    $testStart = Get-Date
    
    try {
        Invoke-Expression $Command
        $exitCode = $LASTEXITCODE
        
        $testEnd = Get-Date
        $elapsed = ($testEnd - $testStart).TotalSeconds
        
        if ($exitCode -eq 0) {
            Write-Success "`n✅ $Name PASADO (${elapsed}s)"
            $script:passedTests++
        } else {
            Write-Error-Custom "`n❌ $Name FALLADO (${elapsed}s)"
            $script:failedTests++
        }
    } catch {
        Write-Error-Custom "`n❌ $Name ERROR: $_"
        $script:failedTests++
    } finally {
        Set-Location $prevLocation
    }
    
    Write-Host ""
}

# Ejecutar según parámetro
switch ($TestSuite) {
    "correctness" {
        Write-Info "🎯 Ejecutando tests de CORRECTITUD..."
        Write-Host ""
        Run-Tests "Tests de Correctitud" "python test_dht_correctness.py correctness" "test"
        $totalTests = 1
    }
    
    "robustness" {
        Write-Info "🛡️  Ejecutando tests de ROBUSTEZ..."
        Write-Host ""
        Run-Tests "Tests de Robustez" "python test_dht_robustness.py robustness" "test"
        $totalTests = 1
    }
    
    "unit" {
        Write-Info "🔬 Ejecutando tests UNITARIOS..."
        Write-Host ""
        Run-Tests "Tests Unitarios" "pytest tests/test_dht_service.py -v" "DistriSearch\backend"
        $totalTests = 1
    }
    
    "integration" {
        Write-Info "🔗 Ejecutando tests de INTEGRACIÓN..."
        Write-Host ""
        Run-Tests "Tests de Integración" "pytest tests/test_dht_routes.py -v" "DistriSearch\backend"
        $totalTests = 1
    }
    
    "e2e" {
        Write-Info "🌐 Ejecutando tests END-TO-END..."
        Write-Warning-Custom "⚠️  Asegúrate de que el backend esté corriendo en http://localhost:8000"
        Write-Host ""
        
        # Verificar si el backend está corriendo
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 2 2>$null
            Write-Success "✅ Backend detectado y funcionando"
        } catch {
            Write-Error-Custom "❌ Backend no está corriendo"
            Write-Info "   Inicia el backend con: cd DistriSearch\backend; uvicorn main:app --reload"
            exit 1
        }
        
        Run-Tests "Smoke Test E2E" "python test_dht_end_to_end.py smoke" "test"
        $totalTests = 1
    }
    
    "smoke" {
        Write-Info "🚀 Ejecutando SMOKE TESTS (rápido)..."
        Write-Host ""
        Run-Tests "Correctitud Rápida" "python test_dht_correctness.py correctness" "test"
        Run-Tests "Robustez Rápida" "python test_dht_robustness.py robustness" "test"
        $totalTests = 2
    }
    
    "all" {
        Write-Info "🎯 Ejecutando TODOS los tests..."
        Write-Host ""
        
        Run-Tests "Tests de Correctitud" "python test_dht_correctness.py correctness" "test"
        Run-Tests "Tests de Robustez" "python test_dht_robustness.py robustness" "test"
        Run-Tests "Tests Unitarios" "pytest tests/test_dht_service.py -v" "DistriSearch\backend"
        Run-Tests "Tests de Integración" "pytest tests/test_dht_routes.py -v" "DistriSearch\backend"
        
        # Verificar backend para E2E
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 2 2>$null
            Write-Success "✅ Backend detectado, ejecutando E2E..."
            Run-Tests "Tests E2E" "python test_dht_end_to_end.py smoke" "test"
            $totalTests = 5
        } catch {
            Write-Warning-Custom "⚠️  Backend no está corriendo, saltando tests E2E"
            $totalTests = 4
        }
    }
    
    default {
        Write-Info "🚀 Ejecutando SMOKE TESTS por defecto..."
        Write-Host ""
        Run-Tests "Correctitud Rápida" "python test_dht_correctness.py correctness" "test"
        Run-Tests "Robustez Rápida" "python test_dht_robustness.py robustness" "test"
        $totalTests = 2
    }
}

# Resumen final
$endTime = Get-Date
$totalElapsed = ($endTime - $startTime).TotalSeconds

Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                     📊 RESUMEN FINAL                       ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "   Suite ejecutada: $TestSuite" -ForegroundColor White
Write-Host "   Tests pasados:   $passedTests / $totalTests" -ForegroundColor $(if ($passedTests -eq $totalTests) { "Green" } else { "Yellow" })
Write-Host "   Tests fallados:  $failedTests" -ForegroundColor $(if ($failedTests -eq 0) { "Green" } else { "Red" })
Write-Host "   Tiempo total:    ${totalElapsed}s" -ForegroundColor White
Write-Host ""

if ($failedTests -eq 0 -and $passedTests -eq $totalTests) {
    Write-Success "🎉 ¡TODOS LOS TESTS PASARON!"
    Write-Host ""
    exit 0
} elseif ($passedTests -gt 0) {
    Write-Warning-Custom "⚠️  ALGUNOS TESTS FALLARON"
    Write-Host ""
    exit 1
} else {
    Write-Error-Custom "❌ TODOS LOS TESTS FALLARON"
    Write-Host ""
    exit 1
}
