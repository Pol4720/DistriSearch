# Inicio Rápido - DistriSearch

## 🚀 Ejecutar Demo en 30 segundos

### 1. Instalar dependencias
```powershell
pip install -r requirements.txt
```

### 2. Ejecutar demo automática
```powershell
python demo.py
```

Esto iniciará una red simulada de 5 nodos, indexará documentos y demostrará:
- ✅ Búsqueda distribuida
- ✅ Ruteo en hipercubo
- ✅ Elección de líder
- ✅ Tolerancia a fallos

---

## 🧪 Ejecutar Tests

### Todos los tests
```powershell
pytest -v
```

### Suite de tests organizada
```powershell
python run_tests.py
```

### Tests específicos
```powershell
# Solo hipercubo
pytest tests/test_hypercube.py -v

# Solo elección de líder
pytest tests/test_election.py -v

# Solo almacenamiento
pytest tests/test_storage.py -v

# Solo integración
pytest tests/test_integration.py -v
```

---

## 🎮 Modo Interactivo

```powershell
python simulator.py --nodes 7
```

Opciones del menú:
1. Ver estado de la red
2. Demo de operaciones básicas
3. Demo de ruteo
4. Demo de elección de líder
5. Añadir documento personalizado
6. Buscar
0. Salir

---

## 🐳 Ejecutar con Docker

### Construir imagen
```powershell
docker build -t distrisearch .
```

### Ejecutar con docker-compose
```powershell
# Iniciar 3 nodos
docker-compose up

# En segundo plano
docker-compose up -d

# Ver logs
docker-compose logs -f

# Detener
docker-compose down
```

### Probar API HTTP
```powershell
# Añadir documento al nodo 0
Invoke-WebRequest -Uri "http://localhost:8000/doc" -Method POST -ContentType "application/json" -Body '{"doc_id": "test1", "content": "Python programming language"}'

# Buscar
Invoke-WebRequest -Uri "http://localhost:8000/search?q=python" -Method GET

# Estado del nodo
Invoke-WebRequest -Uri "http://localhost:8000/status" -Method GET
```

---

## 📊 Estructura de Datos

### Ejemplo de documento
```json
{
  "doc_id": "doc1",
  "content": "Python es un lenguaje de programación",
  "metadata": {
    "author": "usuario",
    "date": "2024-01-01"
  }
}
```

### Ejemplo de resultado de búsqueda
```json
{
  "query": "python",
  "total_results": 2,
  "results": [
    {
      "doc_id": "doc1",
      "score": 3.0,
      "snippet": "Python es un lenguaje...",
      "node_id": 0
    }
  ]
}
```

---

## 🔍 Comandos Útiles

### Ver logs con debug
```powershell
python simulator.py --nodes 5 --debug
```

### Demo automática
```powershell
python simulator.py --nodes 5 --auto
```

### Ejecutar tests con cobertura
```powershell
pytest --cov=. --cov-report=html
# Ver reporte: htmlcov/index.html
```

---

## 🐛 Troubleshooting

### Error: "ModuleNotFoundError"
```powershell
pip install -r requirements.txt
```

### Error en tests
```powershell
# Limpiar cache
Remove-Item -Recurse -Force .pytest_cache
Remove-Item -Recurse -Force __pycache__

# Reinstalar
pip install --upgrade -r requirements.txt
```

### Puerto ocupado (Docker)
```powershell
# Cambiar puertos en docker-compose.yml
# O detener otros servicios
docker-compose down
```

---

## 📚 Más Información

Ver [README.md](README.md) para documentación completa.
