#!/bin/bash

echo "🚀 Inicializando HYPFS con Docker"

# Crear directorios necesarios
mkdir -p data objects results test_files

# Generar docker-compose.yml
echo "📝 Generando docker-compose.yml..."
python compose_gen.py

# Construir imágenes
echo "🔨 Construyendo imágenes Docker..."
docker compose build

# Levantar servicios
echo "🎯 Levantando servicios..."
docker compose up -d

# Esperar a que los servicios estén listos
echo "⏳ Esperando a que los servicios estén listos..."
sleep 10

# Mostrar logs
echo "📊 Estado de los servicios:"
docker compose ps

echo "✅ HYPFS está listo!"
echo ""
echo "Comandos útiles:"
echo "  - Ver logs: docker compose logs -f"
echo "  - Acceder al controller: docker compose exec controller python menu.py"
echo "  - Detener: docker compose down"
echo "  - Ver logs de un nodo: docker compose logs -f hypfs-node-0"