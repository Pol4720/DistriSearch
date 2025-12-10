# DistriSearch Development Setup Script for Windows PowerShell

param(
    [Parameter(Position=0)]
    [ValidateSet("setup", "python", "frontend", "services", "env", "grpc", "run", "run-fe", "help")]
    [string]$Command = "help"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

function Write-Info { param([string]$Message); Write-Host "[INFO] $Message" -ForegroundColor Green }
function Write-Warn { param([string]$Message); Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Write-Error { param([string]$Message); Write-Host "[ERROR] $Message" -ForegroundColor Red }

function Test-Python {
    Write-Info "Checking Python..."
    try {
        $version = python --version 2>&1
        Write-Info "Python version: $version"
        return $true
    }
    catch {
        Write-Error "Python is not installed"
        return $false
    }
}

function Test-Node {
    Write-Info "Checking Node.js..."
    try {
        $version = node --version 2>&1
        Write-Info "Node.js version: $version"
        return $true
    }
    catch {
        Write-Error "Node.js is not installed"
        return $false
    }
}

function Setup-PythonEnv {
    Write-Info "Setting up Python environment..."
    
    Push-Location "$ProjectRoot\backend"
    try {
        if (-not (Test-Path "venv")) {
            python -m venv venv
            Write-Info "Created virtual environment"
        }
        
        # Activate venv and install dependencies
        & ".\venv\Scripts\Activate.ps1"
        pip install --upgrade pip
        pip install -r requirements.txt
        
        Write-Info "Python dependencies installed"
    }
    finally {
        Pop-Location
    }
}

function Setup-Frontend {
    Write-Info "Setting up frontend..."
    
    Push-Location "$ProjectRoot\frontend"
    try {
        if (Test-Path "package.json") {
            npm install
            Write-Info "Frontend dependencies installed"
        }
        else {
            Write-Warn "No package.json found in frontend directory"
        }
    }
    finally {
        Pop-Location
    }
}

function Setup-DevServices {
    Write-Info "Setting up development services..."
    
    Push-Location $ProjectRoot
    try {
        $composeFile = Join-Path $ProjectRoot "docker-compose.dev.yml"
        if (Test-Path $composeFile) {
            docker-compose -f $composeFile up -d mongo redis
            Write-Info "Development services started"
        }
        else {
            Write-Warn "docker-compose.dev.yml not found. Please start MongoDB and Redis manually."
        }
    }
    finally {
        Pop-Location
    }
}

function New-EnvFile {
    Write-Info "Creating .env file..."
    
    $envFile = Join-Path $ProjectRoot "backend\.env"
    
    if (Test-Path $envFile) {
        Write-Warn ".env file already exists. Skipping..."
        return
    }
    
    $envContent = @"
# DistriSearch Environment Configuration

# Application
APP_NAME=DistriSearch
APP_ENV=development
DEBUG=true
LOG_LEVEL=DEBUG

# Server
HOST=0.0.0.0
PORT=8000
WORKERS=1

# MongoDB
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=distrisearch

# Redis
REDIS_URI=redis://localhost:6379

# Cluster
NODE_ID=node-1
CLUSTER_NAME=distrisearch-dev
PARTITION_COUNT=8
REPLICATION_FACTOR=1

# Security
JWT_SECRET=dev-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION=3600

# Rate Limiting
RATE_LIMIT_ENABLED=false
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60

# CORS
CORS_ORIGINS=*
"@

    Set-Content -Path $envFile -Value $envContent
    Write-Info ".env file created"
}

function Generate-GRPC {
    Write-Info "Generating gRPC code..."
    
    Push-Location "$ProjectRoot\backend"
    try {
        & ".\venv\Scripts\Activate.ps1"
        
        $protoDir = Join-Path $ProjectRoot "backend\app\grpc\protos"
        $outDir = Join-Path $ProjectRoot "backend\app\grpc\generated"
        
        if (-not (Test-Path $outDir)) {
            New-Item -ItemType Directory -Path $outDir -Force | Out-Null
        }
        
        Get-ChildItem "$protoDir\*.proto" | ForEach-Object {
            python -m grpc_tools.protoc `
                "-I$protoDir" `
                "--python_out=$outDir" `
                "--grpc_python_out=$outDir" `
                $_.FullName
            Write-Info "Generated code for $($_.Name)"
        }
        
        # Create __init__.py
        New-Item -ItemType File -Path "$outDir\__init__.py" -Force | Out-Null
        
        Write-Info "gRPC code generation complete"
    }
    finally {
        Pop-Location
    }
}

function Start-DevServer {
    Write-Info "Starting development server..."
    
    Push-Location "$ProjectRoot\backend"
    try {
        & ".\venv\Scripts\Activate.ps1"
        uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    }
    finally {
        Pop-Location
    }
}

function Start-FrontendDev {
    Write-Info "Starting frontend development server..."
    
    Push-Location "$ProjectRoot\frontend"
    try {
        npm run dev
    }
    finally {
        Pop-Location
    }
}

function Show-Help {
    Write-Host "DistriSearch Development Setup"
    Write-Host ""
    Write-Host "Usage: .\setup_dev.ps1 <command>"
    Write-Host ""
    Write-Host "Commands:"
    Write-Host "  setup       Full setup (Python + Frontend + Services)"
    Write-Host "  python      Setup Python environment only"
    Write-Host "  frontend    Setup frontend only"
    Write-Host "  services    Start development services (MongoDB, Redis)"
    Write-Host "  env         Create .env file"
    Write-Host "  grpc        Generate gRPC code from proto files"
    Write-Host "  run         Run backend development server"
    Write-Host "  run-fe      Run frontend development server"
    Write-Host "  help        Show this help message"
}

# Main
switch ($Command) {
    "setup" {
        if (-not (Test-Python)) { exit 1 }
        if (-not (Test-Node)) { exit 1 }
        Setup-PythonEnv
        Setup-Frontend
        New-EnvFile
        Setup-DevServices
        Write-Info "Development environment setup complete!"
    }
    "python" {
        if (-not (Test-Python)) { exit 1 }
        Setup-PythonEnv
    }
    "frontend" {
        if (-not (Test-Node)) { exit 1 }
        Setup-Frontend
    }
    "services" {
        Setup-DevServices
    }
    "env" {
        New-EnvFile
    }
    "grpc" {
        Generate-GRPC
    }
    "run" {
        Start-DevServer
    }
    "run-fe" {
        Start-FrontendDev
    }
    default {
        Show-Help
    }
}
