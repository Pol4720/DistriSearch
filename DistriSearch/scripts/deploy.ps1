# DistriSearch Deployment Script for Windows PowerShell

param(
    [Parameter(Position=0)]
    [ValidateSet("init", "build", "deploy", "start", "stop", "status", "logs", "cleanup", "help")]
    [string]$Command = "help",
    
    [Parameter(Position=1)]
    [string]$ServiceName = "api"
)

$ErrorActionPreference = "Stop"

# Configuration
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$ComposeFile = Join-Path $ProjectRoot "docker-compose.swarm.yml"
$StackName = "distrisearch"

# Functions
function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Test-Docker {
    try {
        $null = docker info 2>&1
        return $true
    }
    catch {
        Write-Error "Docker is not running or not installed"
        return $false
    }
}

function Initialize-Swarm {
    Write-Info "Initializing Docker Swarm..."
    
    $swarmInfo = docker info 2>&1 | Select-String "Swarm: active"
    if ($swarmInfo) {
        Write-Info "Swarm is already initialized"
        return
    }
    
    try {
        docker swarm init
    }
    catch {
        Write-Warn "Could not initialize swarm automatically"
        $advertiseAddr = Read-Host "Enter advertise address (e.g., 192.168.1.100)"
        docker swarm init --advertise-addr $advertiseAddr
    }
}

function New-Networks {
    Write-Info "Creating overlay networks..."
    
    try {
        docker network create --driver overlay --attachable distrisearch-network 2>$null
    }
    catch {
        Write-Info "Network may already exist"
    }
}

function New-Volumes {
    Write-Info "Creating volumes..."
    
    @("mongo-data", "redis-data", "distrisearch-data") | ForEach-Object {
        try {
            docker volume create $_ 2>$null
        }
        catch {
            # Volume may already exist
        }
    }
}

function Build-Images {
    Write-Info "Building Docker images..."
    
    Push-Location $ProjectRoot
    try {
        # Build backend image
        docker build -t distrisearch-backend:latest -f docker/Dockerfile.backend .
        
        # Build frontend image
        docker build -t distrisearch-frontend:latest -f docker/Dockerfile.frontend .
    }
    finally {
        Pop-Location
    }
}

function Deploy-Stack {
    Write-Info "Deploying stack..."
    
    docker stack deploy -c $ComposeFile $StackName
}

function Wait-ForServices {
    Write-Info "Waiting for services to be ready..."
    
    $maxWait = 120
    $waited = 0
    
    while ($waited -lt $maxWait) {
        $services = docker service ls --filter "name=$StackName" --format "{{.Replicas}}"
        $ready = ($services | Where-Object { $_ -notmatch "^0/" }).Count
        $total = $services.Count
        
        if ($ready -eq $total -and $total -gt 0) {
            Write-Info "All services are running!"
            return
        }
        
        Start-Sleep -Seconds 5
        $waited += 5
        Write-Info "Waiting... ($waited/$maxWait seconds)"
    }
    
    Write-Warn "Some services may not be fully ready"
}

function Show-Status {
    Write-Info "Stack status:"
    docker stack services $StackName
    Write-Host ""
    Write-Info "Service logs available via: docker service logs ${StackName}_<service>"
}

function Remove-Stack {
    Write-Info "Removing stack..."
    
    try {
        docker stack rm $StackName
    }
    catch {
        # Stack may not exist
    }
    
    Write-Info "Waiting for services to terminate..."
    Start-Sleep -Seconds 10
}

function Invoke-Cleanup {
    Remove-Stack
    
    $removeVolumes = Read-Host "Remove volumes? (y/N)"
    if ($removeVolumes -eq 'y' -or $removeVolumes -eq 'Y') {
        @("mongo-data", "redis-data", "distrisearch-data") | ForEach-Object {
            try {
                docker volume rm $_ 2>$null
            }
            catch {
                # Volume may not exist
            }
        }
    }
    
    $leaveSwarm = Read-Host "Leave swarm? (y/N)"
    if ($leaveSwarm -eq 'y' -or $leaveSwarm -eq 'Y') {
        try {
            docker swarm leave --force 2>$null
        }
        catch {
            # May not be in swarm
        }
    }
}

function Show-Help {
    Write-Host "DistriSearch Deployment Script"
    Write-Host ""
    Write-Host "Usage: .\deploy.ps1 <command> [options]"
    Write-Host ""
    Write-Host "Commands:"
    Write-Host "  init        Initialize swarm, networks, and volumes"
    Write-Host "  build       Build Docker images"
    Write-Host "  deploy      Deploy the stack"
    Write-Host "  start       Full deployment (init + build + deploy)"
    Write-Host "  stop        Remove the stack"
    Write-Host "  status      Show stack status"
    Write-Host "  logs        Show service logs (default: api)"
    Write-Host "  cleanup     Remove everything (stack, volumes, swarm)"
    Write-Host "  help        Show this help message"
}

# Main
if (-not (Test-Docker)) {
    exit 1
}

switch ($Command) {
    "init" {
        Initialize-Swarm
        New-Networks
        New-Volumes
    }
    "build" {
        Build-Images
    }
    "deploy" {
        Deploy-Stack
        Wait-ForServices
        Show-Status
    }
    "start" {
        Initialize-Swarm
        New-Networks
        New-Volumes
        Build-Images
        Deploy-Stack
        Wait-ForServices
        Show-Status
    }
    "stop" {
        Remove-Stack
    }
    "status" {
        Show-Status
    }
    "logs" {
        docker service logs -f "${StackName}_${ServiceName}"
    }
    "cleanup" {
        Invoke-Cleanup
    }
    default {
        Show-Help
    }
}
