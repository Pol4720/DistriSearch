# Preparación de Imágenes Docker

## Construir imágenes
```bash
cd /ruta/a/DistriSearch
docker build -f docker/master/Dockerfile -t distrisearch/master:latest .
docker build -f docker/slave/Dockerfile -t distrisearch/slave:latest .
```

## Guardar para transferir
```bash
docker save distrisearch/master:latest | gzip > distrisearch-master.tar.gz
docker save distrisearch/slave:latest | gzip > distrisearch-slave.tar.gz
```

## Transferir a nodos
```bash
for host in manager1 worker1 worker2; do
    scp distrisearch-*.tar.gz $host:~
done
```

## Cargar en cada nodo
```bash
gunzip -c ~/distrisearch-master.tar.gz | docker load
gunzip -c ~/distrisearch-slave.tar.gz | docker load
docker images | grep distrisearch
```

## Alternativa: registry privado
Usar un Docker Registry local evita transferencias manuales:
```bash
docker tag distrisearch/master:latest registry.local:5000/distrisearch/master:latest
docker push registry.local:5000/distrisearch/master:latest
```