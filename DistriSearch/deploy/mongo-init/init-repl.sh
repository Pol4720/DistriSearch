#!/bin/bash
set -e

# Esperar que los mongod respondan
echo "Esperando que los nodos Mongo estén arriba..."
for i in {1..30}; do
  mongosh --host mongo1:27017 --eval "db.adminCommand('ping')" && break
  sleep 1
done

echo "Iniciando replicaset..."
mongosh --host mongo1:27017 <<'JS'
rs.initiate(
  {
    _id: "rs0",
    members: [
      { _id: 0, host: "mongo1:27017" },
      { _id: 1, host: "mongo2:27017" },
      { _id: 2, host: "mongo3:27017" }
    ]
  }
)
JS

echo "Estableciendo prioridad de miembros y esperando PRIMARY..."
# opción: ajustar prioridades si quieres
sleep 5
mongosh --host mongo1:27017 --eval "rs.status()"
echo "Replica set inicializado."
