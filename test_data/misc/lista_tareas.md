# Lista de Tareas del Proyecto

## 🔴 Alta Prioridad

- [x] Configurar el entorno de desarrollo
- [x] Crear estructura base del proyecto
- [ ] Implementar sistema de autenticación
- [ ] Configurar CI/CD pipeline
- [ ] Escribir tests unitarios para el módulo core

## 🟡 Media Prioridad

- [ ] Documentar API endpoints
- [ ] Crear manual de usuario
- [ ] Optimizar consultas a base de datos
- [ ] Implementar sistema de caché
- [ ] Añadir logging estructurado

## 🟢 Baja Prioridad

- [ ] Mejorar interfaz de usuario
- [ ] Añadir modo oscuro
- [ ] Internacionalización (i18n)
- [ ] Crear video tutorial
- [ ] Actualizar dependencias

## 📅 Calendario

| Semana | Tareas Planificadas | Responsable |
|--------|---------------------|-------------|
| 1 | Auth + Tests | Juan |
| 2 | CI/CD + Docs | María |
| 3 | Caché + Logging | Pedro |
| 4 | Optimización | Todo el equipo |

## 📝 Notas

> Recordar: La demo para el cliente es el día 20. Asegurar que todas las
> funcionalidades críticas estén listas y probadas para esa fecha.

### Comandos útiles

```bash
# Ejecutar tests
pytest -v

# Iniciar servidor de desarrollo
python -m uvicorn app.main:app --reload

# Build de producción
docker-compose up --build
```
