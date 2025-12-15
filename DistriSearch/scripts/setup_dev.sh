#!/bin/bash
# DistriSearch Development Setup Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check Python version
check_python() {
    log_info "Checking Python..."
    
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
        log_info "Python version: $PYTHON_VERSION"
    else
        log_error "Python 3 is not installed"
        exit 1
    fi
}

# Check Node.js version
check_node() {
    log_info "Checking Node.js..."
    
    if command -v node &> /dev/null; then
        NODE_VERSION=$(node --version)
        log_info "Node.js version: $NODE_VERSION"
    else
        log_error "Node.js is not installed"
        exit 1
    fi
}

# Setup Python virtual environment
setup_python_env() {
    log_info "Setting up Python environment..."
    
    cd "$PROJECT_ROOT/backend"
    
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        log_info "Created virtual environment"
    fi
    
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    
    log_info "Python dependencies installed"
}

# Setup frontend
setup_frontend() {
    log_info "Setting up frontend..."
    
    cd "$PROJECT_ROOT/frontend"
    
    if [ -f "package.json" ]; then
        npm install
        log_info "Frontend dependencies installed"
    else
        log_warn "No package.json found in frontend directory"
    fi
}

# Setup development services (MongoDB, Redis)
setup_dev_services() {
    log_info "Setting up development services..."
    
    cd "$PROJECT_ROOT"
    
    if command -v docker-compose &> /dev/null; then
        docker-compose -f docker-compose.dev.yml up -d mongo redis
        log_info "Development services started"
    else
        log_warn "docker-compose not found. Please start MongoDB and Redis manually."
    fi
}

# Create .env file
create_env_file() {
    log_info "Creating .env file..."
    
    ENV_FILE="$PROJECT_ROOT/backend/.env"
    
    if [ -f "$ENV_FILE" ]; then
        log_warn ".env file already exists. Skipping..."
        return
    fi
    
    cat > "$ENV_FILE" << EOF
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
EOF

    log_info ".env file created"
}

# Generate gRPC code
generate_grpc() {
    log_info "Generating gRPC code..."
    
    cd "$PROJECT_ROOT/backend"
    source venv/bin/activate
    
    PROTO_DIR="$PROJECT_ROOT/backend/app/grpc/protos"
    OUT_DIR="$PROJECT_ROOT/backend/app/grpc/generated"
    
    mkdir -p "$OUT_DIR"
    
    for proto_file in "$PROTO_DIR"/*.proto; do
        if [ -f "$proto_file" ]; then
            python -m grpc_tools.protoc \
                -I"$PROTO_DIR" \
                --python_out="$OUT_DIR" \
                --grpc_python_out="$OUT_DIR" \
                "$proto_file"
            log_info "Generated code for $(basename $proto_file)"
        fi
    done
    
    # Create __init__.py
    touch "$OUT_DIR/__init__.py"
    
    log_info "gRPC code generation complete"
}

# Run development server
run_dev() {
    log_info "Starting development server..."
    
    cd "$PROJECT_ROOT/backend"
    source venv/bin/activate
    
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
}

# Run frontend development server
run_frontend_dev() {
    log_info "Starting frontend development server..."
    
    cd "$PROJECT_ROOT/frontend"
    npm run dev
}

# Show help
show_help() {
    echo "DistriSearch Development Setup"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  setup       Full setup (Python + Frontend + Services)"
    echo "  python      Setup Python environment only"
    echo "  frontend    Setup frontend only"
    echo "  services    Start development services (MongoDB, Redis)"
    echo "  env         Create .env file"
    echo "  grpc        Generate gRPC code from proto files"
    echo "  run         Run backend development server"
    echo "  run-fe      Run frontend development server"
    echo "  help        Show this help message"
}

# Main
case "${1:-help}" in
    setup)
        check_python
        check_node
        setup_python_env
        setup_frontend
        create_env_file
        setup_dev_services
        log_info "Development environment setup complete!"
        ;;
    python)
        check_python
        setup_python_env
        ;;
    frontend)
        check_node
        setup_frontend
        ;;
    services)
        setup_dev_services
        ;;
    env)
        create_env_file
        ;;
    grpc)
        generate_grpc
        ;;
    run)
        run_dev
        ;;
    run-fe)
        run_frontend_dev
        ;;
    help|*)
        show_help
        ;;
esac
