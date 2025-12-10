#!/bin/bash
# DistriSearch Deployment Script

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.swarm.yml"
STACK_NAME="distrisearch"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi
}

init_swarm() {
    log_info "Initializing Docker Swarm..."
    
    if docker info | grep -q "Swarm: active"; then
        log_info "Swarm is already initialized"
        return 0
    fi

    docker swarm init || {
        log_warn "Could not initialize swarm automatically. You may need to specify --advertise-addr"
        read -p "Enter advertise address (e.g., 192.168.1.100): " ADVERTISE_ADDR
        docker swarm init --advertise-addr "$ADVERTISE_ADDR"
    }
}

create_networks() {
    log_info "Creating overlay networks..."
    
    docker network create --driver overlay --attachable distrisearch-network 2>/dev/null || true
}

create_volumes() {
    log_info "Creating volumes..."
    
    docker volume create mongo-data 2>/dev/null || true
    docker volume create redis-data 2>/dev/null || true
    docker volume create distrisearch-data 2>/dev/null || true
}

build_images() {
    log_info "Building Docker images..."
    
    cd "$PROJECT_ROOT"
    
    # Build backend image
    docker build -t distrisearch-backend:latest -f docker/Dockerfile.backend .
    
    # Build frontend image
    docker build -t distrisearch-frontend:latest -f docker/Dockerfile.frontend .
}

deploy_stack() {
    log_info "Deploying stack..."
    
    docker stack deploy -c "$COMPOSE_FILE" "$STACK_NAME"
}

wait_for_services() {
    log_info "Waiting for services to be ready..."
    
    local MAX_WAIT=120
    local WAITED=0
    
    while [ $WAITED -lt $MAX_WAIT ]; do
        local REPLICAS=$(docker service ls --filter "name=${STACK_NAME}" --format "{{.Replicas}}" | grep -v "0/" | wc -l)
        local TOTAL=$(docker service ls --filter "name=${STACK_NAME}" --format "{{.Replicas}}" | wc -l)
        
        if [ "$REPLICAS" -eq "$TOTAL" ] && [ "$TOTAL" -gt 0 ]; then
            log_info "All services are running!"
            return 0
        fi
        
        sleep 5
        WAITED=$((WAITED + 5))
        log_info "Waiting... ($WAITED/$MAX_WAIT seconds)"
    done
    
    log_warn "Some services may not be fully ready"
}

show_status() {
    log_info "Stack status:"
    docker stack services "$STACK_NAME"
    echo ""
    log_info "Service logs available via: docker service logs ${STACK_NAME}_<service>"
}

remove_stack() {
    log_info "Removing stack..."
    docker stack rm "$STACK_NAME" || true
    
    log_info "Waiting for services to terminate..."
    sleep 10
}

cleanup() {
    log_info "Cleaning up..."
    
    remove_stack
    
    read -p "Remove volumes? (y/N): " REMOVE_VOLUMES
    if [[ "$REMOVE_VOLUMES" =~ ^[Yy]$ ]]; then
        docker volume rm mongo-data redis-data distrisearch-data 2>/dev/null || true
    fi
    
    read -p "Leave swarm? (y/N): " LEAVE_SWARM
    if [[ "$LEAVE_SWARM" =~ ^[Yy]$ ]]; then
        docker swarm leave --force 2>/dev/null || true
    fi
}

show_help() {
    echo "DistriSearch Deployment Script"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  init        Initialize swarm, networks, and volumes"
    echo "  build       Build Docker images"
    echo "  deploy      Deploy the stack"
    echo "  start       Full deployment (init + build + deploy)"
    echo "  stop        Remove the stack"
    echo "  status      Show stack status"
    echo "  logs        Show service logs"
    echo "  cleanup     Remove everything (stack, volumes, swarm)"
    echo "  help        Show this help message"
}

# Main
case "${1:-help}" in
    init)
        check_docker
        init_swarm
        create_networks
        create_volumes
        ;;
    build)
        check_docker
        build_images
        ;;
    deploy)
        check_docker
        deploy_stack
        wait_for_services
        show_status
        ;;
    start)
        check_docker
        init_swarm
        create_networks
        create_volumes
        build_images
        deploy_stack
        wait_for_services
        show_status
        ;;
    stop)
        check_docker
        remove_stack
        ;;
    status)
        check_docker
        show_status
        ;;
    logs)
        check_docker
        SERVICE="${2:-api}"
        docker service logs -f "${STACK_NAME}_${SERVICE}"
        ;;
    cleanup)
        check_docker
        cleanup
        ;;
    help|*)
        show_help
        ;;
esac
