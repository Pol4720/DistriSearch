#!/usr/bin/env bash
# DistriSearch - Script de inicio DHT (Bash)
# Ejecutar desde la raíz del proyecto: ./DistriSearch/scripts/start_dht.sh
# Soporta: modo (external|inproc), DhtPort, BackendPort, SeedIP, --skip-frontend

set -euo pipefail

# Defaults
MODE="external"
DHT_PORT=2000
BACKEND_PORT=8000
SEED_IP=""
SKIP_FRONTEND=0

print_usage() {
  cat <<EOF
Uso: $0 [--mode external|inproc] [--dht-port N] [--backend-port N] [--seed-ip IP] [--skip-frontend]

Opciones:
  --mode            Modo DHT: 'external' (por defecto) o 'inproc'
  --dht-port        Puerto DHT (por defecto 2000)
  --backend-port    Puerto Backend (por defecto 8000)
  --seed-ip         IP de una seed para conectar/bootstrapping
  --skip-frontend   No iniciar frontend
  -h, --help        Muestra esta ayuda

Ejemplo:
  $0 --mode inproc --dht-port 2001 --backend-port 8000 --seed-ip 192.168.1.10
EOF
}

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="$2"; shift 2;;
    --dht-port)
      DHT_PORT="$2"; shift 2;;
    --backend-port)
      BACKEND_PORT="$2"; shift 2;;
    --seed-ip)
      SEED_IP="$2"; shift 2;;
    --skip-frontend)
      SKIP_FRONTEND=1; shift 1;;
    -h|--help)
      print_usage; exit 0;;
    *)
      echo "Opción desconocida: $1"; print_usage; exit 1;;
  esac
done

# Check running from project root
if [[ ! -f "./DistriSearch/backend/main.py" ]]; then
  echo "❌ Error: Ejecuta este script desde la raíz del proyecto (donde está la carpeta DistriSearch)"
  echo "   Ejemplo: ./DistriSearch/scripts/start_dht.sh"
  exit 1
fi

# Helper: open new terminal with fallback
open_in_new_terminal() {
  local title="$1"; shift
  local cmd="$*"
  # Commands to try (Linux, macOS, many distros). Each one will run the command and wait for a key.
  if command -v gnome-terminal >/dev/null 2>&1; then
    gnome-terminal -- bash -lc "echo -e \"═══════════════════════════════════════\"; echo \" $title \"; echo -e \"═══════════════════════════════════════\"; echo; $cmd; echo; read -n1 -s -r -p 'Proceso finalizado. Presiona cualquier tecla para cerrar...';"
    return
  fi
  if command -v konsole >/dev/null 2>&1; then
    konsole -e bash -lc "echo -e \"═══════════════════════════════════════\"; echo \" $title \"; echo -e \"═══════════════════════════════════════\"; echo; $cmd; echo; read -n1 -s -r -p 'Proceso finalizado. Presiona cualquier tecla para cerrar...';"
    return
  fi
  if command -v xfce4-terminal >/dev/null 2>&1; then
    xfce4-terminal --hold -e "bash -lc \"$cmd; echo; read -n1 -s -r -p 'Proceso finalizado. Presiona cualquier tecla para cerrar...';\""
    return
  fi
  if command -v xterm >/dev/null 2>&1; then
    xterm -hold -T "$title" -e bash -lc "$cmd; read -n1 -s -r -p 'Proceso finalizado. Presiona cualquier tecla para cerrar...';"
    return
  fi
  # macOS Terminal.app
  if [[ "$(uname)" == "Darwin" ]] && command -v osascript >/dev/null 2>&1; then
    osascript -e "tell application \"Terminal\" to do script \"$cmd; echo; read -n1 -s -r -p 'Proceso finalizado. Presiona cualquier tecla para cerrar...'\""
    return
  fi
  # Fallback: run in background and log output
  local logfile="./.${title// /_}.log"
  echo "⚠️  No se detectó un emulador de terminal soportado. Ejecutando en background, logs: $logfile"
  bash -c "$cmd" > "$logfile" 2>&1 &
}

# Start services
echo "╔════════════════════════════════════════════════════════════╗"
echo "║       DistriSearch - Inicio con DHT (Bash)                 ║"
echo "╚════════════════════════════════════════════════════════════╝"

echo "📋 Configuración:"
echo "   Modo DHT: $MODE"
echo "   Puerto DHT: $DHT_PORT"
echo "   Puerto Backend: $BACKEND_PORT"
if [[ -n "$SEED_IP" ]]; then echo "   Seed IP: $SEED_IP"; fi

echo

# 1. Iniciar DHT si es modo external
if [[ "$MODE" == "external" ]]; then
  echo "📡 Iniciando servicio DHT externo..."
  DHT_DIR="./DHT"
  if [[ -d "$DHT_DIR" && -f "$DHT_DIR/main.py" ]]; then
    open_in_new_terminal "DHT Service (Flask)" "cd '$DHT_DIR' && echo 'Iniciando DHT (python main.py)...' && python main.py"
    sleep 3
  else
    echo "⚠️  No se encontró la carpeta DHT con main.py en ./DHT. Saltando inicio externo DHT."
  fi
fi

# 2. Configurar y arrancar backend
echo "⚙️  Configurando backend..."

# Prepare environment for backend command
BACKEND_DIR="./DistriSearch/backend"
if [[ ! -d "$BACKEND_DIR" ]]; then
  echo "❌ No se encontró $BACKEND_DIR"
  exit 1
fi

# Create the command that sets env vars then runs uvicorn
BACKEND_CMD="export DHT_AUTO_START=true; export DHT_MODE='$MODE'; export DHT_PORT=$DHT_PORT;"
if [[ "$MODE" == "external" ]]; then
  BACKEND_CMD+=" export DHT_HTTP_URL='http://127.0.0.1:8080';"
fi
if [[ -n "$SEED_IP" ]]; then
  BACKEND_CMD+=" export DHT_SEED_IP='$SEED_IP'; export DHT_SEED_PORT=$DHT_PORT;"
fi
BACKEND_CMD+=" uvicorn main:app --reload --host 0.0.0.0 --port $BACKEND_PORT"

open_in_new_terminal "Backend API" "cd '$BACKEND_DIR' && echo 'Iniciando Backend: $BACKEND_CMD' && $BACKEND_CMD"
sleep 5

# 3. Iniciar frontend
if [[ $SKIP_FRONTEND -eq 0 ]]; then
  FRONTEND_DIR="./DistriSearch/frontend"
  if [[ -d "$FRONTEND_DIR" && -f "$FRONTEND_DIR/app.py" ]]; then
    echo "🎨 Iniciando frontend..."
    open_in_new_terminal "Frontend (Streamlit)" "cd '$FRONTEND_DIR' && echo 'streamlit run app.py' && streamlit run app.py"
  else
    echo "⚠️  No se encontró frontend en $FRONTEND_DIR. Saltando frontend."
  fi
fi

# Summary
echo
echo "✅ Todos los servicios iniciados (o lanzados)."
echo
echo "📍 URLs de acceso:"
if [[ "$MODE" == "external" ]]; then
  echo "   DHT API:      http://localhost:8080"
fi
echo "   Backend API:  http://localhost:$BACKEND_PORT"
echo "   Documentación: http://localhost:$BACKEND_PORT/docs"
if [[ $SKIP_FRONTEND -eq 0 ]]; then
  echo "   Frontend:     http://localhost:8501"
fi

echo
echo "💡 Consejos:"
echo "   • Usa Ctrl+C en cada ventana para detener los servicios (o mata los procesos si se lanzaron en background)."
echo "   • Revisa los logs generados en ./ (archivos .*.log) si no se pudo abrir una terminal nueva."
echo "   • Para unirte a una seed, usa la UI del frontend o la API"
echo
echo "📚 Documentación completa: DistriSearch/DHT_INTEGRATION_GUIDE.md"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Ejemplos de uso:" 
echo "  $0 --mode external"
echo "  $0 --mode inproc"
echo "  $0 --mode inproc --seed-ip 192.168.1.10"
echo "  $0 --mode inproc --skip-frontend"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
