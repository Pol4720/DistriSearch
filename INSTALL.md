# Guía de Instalación - DistriSearch

## 📋 Requisitos Previos

### Software Necesario
- **Python**: 3.11 o superior
  - Descargar: https://www.python.org/downloads/
  - Durante instalación, marcar "Add Python to PATH"
  
- **pip**: Viene incluido con Python 3.11+
  - Verificar: `python --version` y `pip --version`

- **Docker** (opcional, solo para modo contenedores)
  - Descargar: https://www.docker.com/products/docker-desktop/
  - Incluye docker-compose

- **Git** (opcional, para clonar repositorio)
  - Descargar: https://git-scm.com/downloads

## 🚀 Instalación Paso a Paso

### Opción 1: Instalación Estándar (Recomendada)

#### Paso 1: Navegar al directorio del proyecto
```powershell
cd e:\Proyectos\DistriSearch
```

#### Paso 2: Verificar versión de Python
```powershell
python --version
# Debe mostrar: Python 3.11.x o superior
```

#### Paso 3: (Opcional) Crear entorno virtual
```powershell
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
.\venv\Scripts\Activate.ps1

# Si hay error de permisos, ejecutar primero:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### Paso 4: Instalar dependencias
```powershell
pip install -r requirements.txt
```

Dependencias que se instalarán:
- `aiohttp` - Servidor HTTP asíncrono
- `pytest` - Framework de testing
- `pytest-asyncio` - Soporte para tests async

#### Paso 5: Verificar instalación
```powershell
# Comprobar que no hay errores de sintaxis
python -m py_compile hypercube.py election.py storage.py network.py databalancer.py node.py simulator.py

# Si no hay output, ¡todo está bien! ✓
```

#### Paso 6: Ejecutar demo
```powershell
python demo.py
```

Si ves output como esto, ¡la instalación fue exitosa!:
```
══════════════════════════════════════════════════════════════════
 DistriSearch - Buscador Distribuido con Hipercubo
══════════════════════════════════════════════════════════════════

[1/5] Creando red de 5 nodos...
...
```

### Opción 2: Instalación con Docker

#### Paso 1: Verificar Docker
```powershell
docker --version
docker-compose --version
```

#### Paso 2: Construir imagen
```powershell
docker build -t distrisearch .
```

Este proceso puede tomar varios minutos la primera vez.

#### Paso 3: Iniciar contenedores
```powershell
docker-compose up
```

Verás logs de 3 nodos iniciándose.

#### Paso 4: Probar API (en otra terminal)
```powershell
# Añadir documento
Invoke-WebRequest -Uri "http://localhost:8000/doc" -Method POST -ContentType "application/json" -Body '{"doc_id": "test1", "content": "Python programming"}'

# Buscar
Invoke-WebRequest -Uri "http://localhost:8000/search?q=python" -Method GET
```

#### Paso 5: Detener contenedores
```powershell
docker-compose down
```

## ✅ Verificación de la Instalación

### Test 1: Ejecutar tests unitarios
```powershell
pytest -v
```

**Resultado esperado**: Todos los tests pasan (pueden haber algunos warnings, es normal).

### Test 2: Ejecutar simulador interactivo
```powershell
python simulator.py --nodes 5
```

**Resultado esperado**: Menú interactivo se muestra.

### Test 3: Comprobar módulos
```powershell
python -c "import hypercube, election, storage, network, databalancer, node; print('✓ Todos los módulos importados correctamente')"
```

**Resultado esperado**: `✓ Todos los módulos importados correctamente`

## 🐛 Solución de Problemas

### Problema 1: "python no se reconoce como comando"

**Causa**: Python no está en PATH.

**Solución**:
1. Reinstalar Python marcando "Add Python to PATH"
2. O añadir manualmente a PATH:
   - Sistema → Configuración avanzada → Variables de entorno
   - Añadir `C:\Python311` y `C:\Python311\Scripts` a PATH

### Problema 2: "ModuleNotFoundError: No module named 'aiohttp'"

**Causa**: Dependencias no instaladas.

**Solución**:
```powershell
pip install -r requirements.txt
```

### Problema 3: Error de permisos en PowerShell

**Causa**: Política de ejecución restrictiva.

**Solución**:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Problema 4: Tests fallan con errores de importación

**Causa**: Python no encuentra los módulos.

**Solución**:
```powershell
# Asegurarse de estar en el directorio correcto
cd e:\Proyectos\DistriSearch

# Ejecutar tests desde el directorio raíz
pytest -v
```

### Problema 5: Docker no inicia

**Causa**: Docker Desktop no está ejecutándose.

**Solución**:
1. Abrir Docker Desktop
2. Esperar a que esté "running"
3. Reintentar `docker-compose up`

### Problema 6: Puerto 8000 ya en uso

**Causa**: Otro programa usa el puerto.

**Solución**:
```powershell
# Ver qué proceso usa el puerto
netstat -ano | findstr :8000

# Matar proceso (reemplazar PID)
taskkill /PID <PID> /F

# O cambiar puerto en simulator.py o docker-compose.yml
```

## 🔄 Actualización

Si hay cambios en el código:

```powershell
# Actualizar dependencias
pip install --upgrade -r requirements.txt

# Limpiar cache
.\commands.ps1 clean

# Recompilar (si usas Docker)
docker-compose build --no-cache
```

## 🧹 Desinstalación

### Desinstalar paquetes Python
```powershell
pip uninstall -r requirements.txt -y
```

### Eliminar entorno virtual
```powershell
Remove-Item -Recurse -Force venv
```

### Limpiar datos y cache
```powershell
.\commands.ps1 clean-all
```

### Limpiar Docker
```powershell
docker-compose down --rmi all --volumes
docker rmi distrisearch
```

## 📞 Soporte

Si encuentras problemas:

1. **Revisa logs**:
   ```powershell
   # Ver archivo de log
   Get-Content distrisearch.log -Tail 50
   ```

2. **Ejecuta con debug**:
   ```powershell
   python simulator.py --debug
   ```

3. **Verifica versiones**:
   ```powershell
   python --version
   pip list
   ```

## ✨ Próximos Pasos

Una vez instalado correctamente:

1. 📖 Lee [QUICKSTART.md](QUICKSTART.md) para comandos básicos
2. 🏗️ Explora [ARCHITECTURE.md](ARCHITECTURE.md) para entender el diseño
3. 📚 Consulta [README.md](README.md) para referencia completa
4. 🎮 Experimenta con `python simulator.py --nodes 7`
5. 🧪 Ejecuta tests con `pytest -v`

---

**¡Listo!** El sistema está instalado y funcionando. 🎉
