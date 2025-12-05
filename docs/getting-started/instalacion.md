# Instalación

Esta guía te llevará paso a paso por la instalación de DistriSearch en diferentes entornos.

---

## 📦 Métodos de Instalación

<div class="grid cards" markdown>

-   :material-docker:{ .lg .middle } __Docker Compose__

    ---

    Forma más rápida y sencilla. Recomendado para principiantes.

    [:octicons-arrow-right-24: Ver guía](#docker-compose)

-   :material-language-python:{ .lg .middle } __Instalación Local__

    ---

    Para desarrollo o personalización avanzada.

    [:octicons-arrow-right-24: Ver guía](#instalacion-local)

-   :material-kubernetes:{ .lg .middle } __Docker Swarm__

    ---

    Para producción con alta disponibilidad.

    [:octicons-arrow-right-24: Ver guía](#docker-swarm)

-   :material-cloud:{ .lg .middle } __Kubernetes__

    ---

    Para entornos cloud enterprise.

    [:octicons-arrow-right-24: Ver guía](#kubernetes)

</div>

---

## 🐳 Docker Compose

### Requisitos

- Docker 20.10+
- Docker Compose 2.0+
- 4 GB RAM disponible
- 10 GB espacio en disco

### Paso 1: Clonar Repositorio

```bash
git clone https://github.com/Pol4720/DS-Project.git
cd DistriSearch/deploy
```

### Paso 2: Configurar Variables de Entorno

```bash
# Crear archivo .env
cat > .env << EOF
# Backend
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000

# Frontend
FRONTEND_PORT=8501

# Agente 1
AGENT1_PORT=5001
AGENT1_FOLDER=./shared_folders/agent1

# Agente 2
AGENT2_PORT=5002
AGENT2_FOLDER=./shared_folders/agent2
EOF
```

### Paso 3: Iniciar Servicios

```bash
docker-compose up -d
```

### Paso 4: Verificar Estado

```bash
# Ver contenedores
docker-compose ps

# Debe mostrar:
# NAME                SERVICE    STATUS        PORTS
# backend             backend    Up 30 seconds 0.0.0.0:8000->8000/tcp
# frontend            frontend   Up 30 seconds 0.0.0.0:8501->8501/tcp
# agent1              agent1     Up 30 seconds 0.0.0.0:5001->5001/tcp
# agent2              agent2     Up 30 seconds 0.0.0.0:5002->5002/tcp
```

### Paso 5: Acceder a la Interfaz

| Servicio | URL | Descripción |
|----------|-----|-------------|
| **Frontend** | http://localhost:8501 | Interfaz web principal |
| **Backend API** | http://localhost:8000 | API REST |
| **Swagger Docs** | http://localhost:8000/docs | Documentación interactiva |
| **Agente 1** | http://localhost:5001 | Nodo 1 |
| **Agente 2** | http://localhost:5002 | Nodo 2 |

### Gestión de Contenedores

```bash
# Detener servicios
docker-compose stop

# Reiniciar servicios
docker-compose restart

# Ver logs
docker-compose logs -f

# Ver logs de un servicio específico
docker-compose logs -f backend

# Eliminar servicios
docker-compose down

# Eliminar con volúmenes
docker-compose down -v
```

---

## 💻 Instalación Local

### Requisitos

- Python 3.8 o superior
- pip 20.0+
- virtualenv (recomendado)
- 2 GB RAM disponible

### Paso 1: Clonar Repositorio

```bash
git clone https://github.com/Pol4720/DS-Project.git
cd DistriSearch
```

### Paso 2: Crear Entorno Virtual

=== "Linux/Mac"

    ```bash
    # Crear entorno virtual
    python3 -m venv venv
    
    # Activar entorno
    source venv/bin/activate
    ```

=== "Windows"

    ```powershell
    # Crear entorno virtual
    python -m venv venv
    
    # Activar entorno
    .\venv\Scripts\Activate.ps1
    
    # Si hay error de ejecución de scripts
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
    ```

### Paso 3: Instalar Backend

```bash
cd backend

# Instalar dependencias
pip install -r requirements.txt

# Verificar instalación
python -c "import fastapi; print(fastapi.__version__)"
```

??? info "Dependencias del Backend"
    ```txt
    fastapi==0.109.0
    uvicorn[standard]==0.27.0
    sqlalchemy==2.0.25
    pydantic==2.5.3
    python-multipart==0.0.6
    aiohttp==3.9.1
    ```

### Paso 4: Instalar Frontend

```bash
cd ../frontend

# Instalar dependencias
pip install -r requirements.txt

# Verificar instalación
streamlit --version
```

??? info "Dependencias del Frontend"
    ```txt
    streamlit==1.32.0
    requests==2.31.0
    plotly==5.18.0
    streamlit-extras==0.3.6
    streamlit-option-menu==0.3.6
    ```

### Paso 5: Instalar Agente

```bash
cd ../agent

# Instalar dependencias
pip install -r requirements.txt
```

??? info "Dependencias del Agente"
    ```txt
    fastapi==0.109.0
    uvicorn==0.27.0
    requests==2.31.0
    pyyaml==6.0.1
    watchdog==3.0.0
    ```

### Paso 6: Configurar Agente

```bash
# Copiar config de ejemplo
cp config.yaml.example config.yaml

# Editar configuración
nano config.yaml
```

```yaml
# config.yaml
agent:
  node_id: "my-node-1"
  name: "Mi Primer Nodo"
  shared_folder: "/path/to/shared/folder"  # Cambiar esto
  port: 5001

backend:
  url: "http://localhost:8000"
  register_on_start: true

scan:
  interval: 300  # 5 minutos
  file_types:
    - ".pdf"
    - ".docx"
    - ".txt"
    - ".xlsx"
```

### Paso 7: Iniciar Servicios

Necesitarás **3 terminales diferentes**:

=== "Terminal 1: Backend"

    ```bash
    cd backend
    source ../venv/bin/activate  # Si usas venv
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
    ```

=== "Terminal 2: Frontend"

    ```bash
    cd frontend
    source ../venv/bin/activate  # Si usas venv
    streamlit run app.py --server.port 8501
    ```

=== "Terminal 3: Agente"

    ```bash
    cd agent
    source ../venv/bin/activate  # Si usas venv
    python agent.py
    ```

### Paso 8: Verificar Instalación

```bash
# Backend health check
curl http://localhost:8000/health

# Frontend (navegar en navegador)
# http://localhost:8501

# Agente health check
curl http://localhost:5001/health
```

---

## 🐝 Docker Swarm

Para producción con múltiples hosts.

### Requisitos

- Docker 20.10+ en todos los nodos
- Nodos con conectividad de red
- Puertos abiertos: 2377, 7946, 4789

### Paso 1: Inicializar Swarm

```bash
# En el nodo manager
docker swarm init --advertise-addr <MANAGER-IP>

# Guardar el token que aparece
```

### Paso 2: Unir Nodos Workers

```bash
# En cada nodo worker
docker swarm join --token <TOKEN> <MANAGER-IP>:2377
```

### Paso 3: Verificar Cluster

```bash
# En el manager
docker node ls

# Debe mostrar todos los nodos
```

### Paso 4: Desplegar Stack

```bash
# Clonar repo en manager
git clone https://github.com/Pol4720/DS-Project.git
cd DistriSearch/deploy

# Desplegar stack
docker stack deploy -c docker-stack.yml distrisearch
```

### Paso 5: Verificar Servicios

```bash
# Ver servicios
docker service ls

# Ver réplicas
docker service ps distrisearch_backend
docker service ps distrisearch_frontend

# Ver logs
docker service logs distrisearch_backend
```

### Configuración del Stack

```yaml
# docker-stack.yml
version: "3.8"

services:
  backend:
    image: distrisearch/backend:latest
    deploy:
      replicas: 3
      restart_policy:
        condition: on-failure
      resources:
        limits:
          cpus: '2'
          memory: 2G
    ports:
      - "8000:8000"
    networks:
      - distrisearch-net

  frontend:
    image: distrisearch/frontend:latest
    deploy:
      replicas: 2
    ports:
      - "8501:8501"
    networks:
      - distrisearch-net

  agent:
    image: distrisearch/agent:latest
    deploy:
      mode: global  # Una réplica por nodo
    ports:
      - "5001:5001"
    volumes:
      - agent-data:/app/shared
    networks:
      - distrisearch-net

networks:
  distrisearch-net:
    driver: overlay

volumes:
  agent-data:
```

### Escalar Servicios

```bash
# Escalar backend a 5 réplicas
docker service scale distrisearch_backend=5

# Escalar frontend a 3 réplicas
docker service scale distrisearch_frontend=3
```

---

## ☸️ Kubernetes

Para entornos cloud enterprise.

### Requisitos

- Kubernetes 1.20+
- kubectl configurado
- 8 GB RAM total en el cluster
- Storage class disponible

### Paso 1: Crear Namespace

```bash
kubectl create namespace distrisearch
```

### Paso 2: Aplicar Manifiestos

```bash
# Clonar repositorio
git clone https://github.com/Pol4720/DS-Project.git
cd DistriSearch/k8s

# Aplicar configuraciones
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secrets.yaml
kubectl apply -f backend-deployment.yaml
kubectl apply -f frontend-deployment.yaml
kubectl apply -f agent-daemonset.yaml
kubectl apply -f services.yaml
kubectl apply -f ingress.yaml
```

### Paso 3: Verificar Despliegue

```bash
# Ver pods
kubectl get pods -n distrisearch

# Ver servicios
kubectl get svc -n distrisearch

# Ver logs
kubectl logs -f -n distrisearch deployment/backend
```

### Manifiestos de Kubernetes

=== "backend-deployment.yaml"

    ```yaml
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: backend
      namespace: distrisearch
    spec:
      replicas: 3
      selector:
        matchLabels:
          app: backend
      template:
        metadata:
          labels:
            app: backend
        spec:
          containers:
          - name: backend
            image: distrisearch/backend:latest
            ports:
            - containerPort: 8000
            resources:
              requests:
                memory: "512Mi"
                cpu: "500m"
              limits:
                memory: "2Gi"
                cpu: "2000m"
            livenessProbe:
              httpGet:
                path: /health
                port: 8000
              initialDelaySeconds: 30
              periodSeconds: 10
            readinessProbe:
              httpGet:
                path: /health
                port: 8000
              initialDelaySeconds: 5
              periodSeconds: 5
    ```

=== "frontend-deployment.yaml"

    ```yaml
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: frontend
      namespace: distrisearch
    spec:
      replicas: 2
      selector:
        matchLabels:
          app: frontend
      template:
        metadata:
          labels:
            app: frontend
        spec:
          containers:
          - name: frontend
            image: distrisearch/frontend:latest
            ports:
            - containerPort: 8501
            env:
            - name: BACKEND_URL
              value: "http://backend:8000"
    ```

=== "agent-daemonset.yaml"

    ```yaml
    apiVersion: apps/v1
    kind: DaemonSet
    metadata:
      name: agent
      namespace: distrisearch
    spec:
      selector:
        matchLabels:
          app: agent
      template:
        metadata:
          labels:
            app: agent
        spec:
          containers:
          - name: agent
            image: distrisearch/agent:latest
            ports:
            - containerPort: 5001
            volumeMounts:
            - name: shared-data
              mountPath: /app/shared
          volumes:
          - name: shared-data
            hostPath:
              path: /mnt/shared
              type: DirectoryOrCreate
    ```

### Exponer con Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: distrisearch-ingress
  namespace: distrisearch
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  rules:
  - host: distrisearch.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend
            port:
              number: 8501
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: backend
            port:
              number: 8000
```

---

## 🔧 Configuración Post-Instalación

### 1. Verificar Servicios

```bash
# Health checks
curl http://localhost:8000/health
curl http://localhost:5001/health

# Ver nodos registrados
curl http://localhost:8000/nodes/

# Ver archivos indexados
curl http://localhost:8000/files/
```

### 2. Crear Carpetas Compartidas

```bash
# Crear estructura de carpetas
mkdir -p ~/distrisearch/shared1
mkdir -p ~/distrisearch/shared2

# Agregar archivos de prueba
echo "Test document" > ~/distrisearch/shared1/test.txt
```

### 3. Configurar Firewall

=== "Linux (ufw)"

    ```bash
    # Abrir puertos
    sudo ufw allow 8000/tcp  # Backend
    sudo ufw allow 8501/tcp  # Frontend
    sudo ufw allow 5001/tcp  # Agente 1
    sudo ufw allow 5002/tcp  # Agente 2
    ```

=== "Windows"

    ```powershell
    # Abrir puertos en Firewall
    New-NetFirewallRule -DisplayName "DistriSearch Backend" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
    New-NetFirewallRule -DisplayName "DistriSearch Frontend" -Direction Inbound -LocalPort 8501 -Protocol TCP -Action Allow
    ```

---

## ✅ Checklist de Instalación

- [ ] Python 3.8+ instalado
- [ ] Repositorio clonado
- [ ] Dependencias instaladas
- [ ] Backend iniciado y respondiendo en :8000
- [ ] Frontend iniciado y accesible en :8501
- [ ] Al menos 1 agente configurado y corriendo
- [ ] Agente registrado en backend
- [ ] Carpeta compartida configurada
- [ ] Primer escaneo completado
- [ ] Primera búsqueda exitosa

---

## 🆘 Solución de Problemas

### Error: Puerto ya en uso

```bash
# Linux/Mac
lsof -ti:8000 | xargs kill -9

# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### Error: Módulo no encontrado

```bash
# Reinstalar dependencias
pip install --force-reinstall -r requirements.txt
```

### Error: Permiso denegado

```bash
# Linux/Mac
chmod +x agent.py
sudo chown -R $USER:$USER ~/distrisearch
```

### Docker: Contenedor no inicia

```bash
# Ver logs detallados
docker-compose logs backend

# Reconstruir imagen
docker-compose build --no-cache backend
docker-compose up -d backend
```

---

[:octicons-arrow-left-24: Volver a Comenzar](index.md){ .md-button }
[:octicons-arrow-right-24: Configuración](configuracion.md){ .md-button .md-button--primary }
