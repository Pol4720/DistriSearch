# API Reference

Documentación completa de los endpoints REST de DistriSearch.

---

## 🌐 URL Base

```
http://localhost:8000
```

Todas las rutas son relativas a esta URL base.

---

## 🔍 Búsqueda

### Buscar Archivos

Realiza una búsqueda distribuida en todos los nodos activos.

```http
GET /search/
```

#### Parámetros

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `q` | string | ✅ | Término de búsqueda |
| `max_results` | integer | ❌ | Máximo de resultados (default: 50) |
| `file_type` | string | ❌ | Filtrar por tipo (.pdf, .docx, etc.) |
| `node_id` | string | ❌ | Buscar solo en un nodo específico |

#### Ejemplo de Petición

```bash
curl "http://localhost:8000/search/?q=proyecto&max_results=10"
```

#### Ejemplo de Respuesta

```json
{
  "files": [
    {
      "file_id": "abc123def456",
      "name": "proyecto_final.pdf",
      "path": "/documents/proyecto_final.pdf",
      "size": 2048576,
      "file_type": "pdf",
      "score": 9.2,
      "node_id": "node-001",
      "node_name": "Oficina Principal",
      "indexed_at": "2024-01-15T10:30:00Z",
      "modified_at": "2024-01-14T15:20:00Z"
    },
    {
      "file_id": "xyz789abc123",
      "name": "proyecto_diseño.docx",
      "path": "/shared/proyecto_diseño.docx",
      "size": 524288,
      "file_type": "docx",
      "score": 8.7,
      "node_id": "node-002",
      "node_name": "Oficina Secundaria",
      "indexed_at": "2024-01-15T09:15:00Z",
      "modified_at": "2024-01-13T11:45:00Z"
    }
  ],
  "total": 2,
  "query": "proyecto",
  "query_time_ms": 245,
  "nodes_searched": 2,
  "nodes_responded": 2
}
```

#### Códigos de Estado

| Código | Descripción |
|--------|-------------|
| `200` | Búsqueda exitosa |
| `400` | Parámetros inválidos |
| `500` | Error del servidor |

---

## 📁 Archivos

### Listar Todos los Archivos

```http
GET /files/
```

#### Parámetros

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `skip` | integer | ❌ | Offset para paginación (default: 0) |
| `limit` | integer | ❌ | Límite de resultados (default: 100) |
| `node_id` | string | ❌ | Filtrar por nodo |

#### Ejemplo de Petición

```bash
curl "http://localhost:8000/files/?limit=20&node_id=node-001"
```

#### Ejemplo de Respuesta

```json
{
  "files": [
    {
      "file_id": "abc123",
      "name": "documento.pdf",
      "size": 1048576,
      "file_type": "pdf",
      "node_id": "node-001",
      "indexed_at": "2024-01-15T10:00:00Z"
    }
  ],
  "total": 150,
  "skip": 0,
  "limit": 20
}
```

### Obtener Información de un Archivo

```http
GET /files/{file_id}
```

#### Parámetros de Ruta

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `file_id` | string | ID único del archivo |

#### Ejemplo de Petición

```bash
curl "http://localhost:8000/files/abc123def456"
```

#### Ejemplo de Respuesta

```json
{
  "file_id": "abc123def456",
  "name": "proyecto_final.pdf",
  "path": "/documents/proyecto_final.pdf",
  "size": 2048576,
  "file_type": "pdf",
  "checksum": "sha256:abcdef123456...",
  "node_id": "node-001",
  "node": {
    "node_id": "node-001",
    "name": "Oficina Principal",
    "ip_address": "192.168.1.100",
    "port": 5001,
    "status": "online"
  },
  "metadata": {
    "title": "Proyecto Final",
    "author": "Juan Pérez",
    "created": "2024-01-10T08:00:00Z"
  },
  "indexed_at": "2024-01-15T10:30:00Z",
  "modified_at": "2024-01-14T15:20:00Z"
}
```

#### Códigos de Estado

| Código | Descripción |
|--------|-------------|
| `200` | Archivo encontrado |
| `404` | Archivo no existe |

---

## 📥 Descarga

### Descargar Archivo

```http
GET /download/{file_id}
```

#### Parámetros de Ruta

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `file_id` | string | ID único del archivo |

#### Ejemplo de Petición

```bash
curl -O -J "http://localhost:8000/download/abc123def456"
```

#### Respuesta

Devuelve el archivo binario con headers apropiados:

```http
HTTP/1.1 200 OK
Content-Type: application/pdf
Content-Disposition: attachment; filename="proyecto_final.pdf"
Content-Length: 2048576

[Binary file data]
```

#### Códigos de Estado

| Código | Descripción |
|--------|-------------|
| `200` | Descarga exitosa |
| `404` | Archivo no encontrado |
| `503` | Nodo offline |

---

## 🌐 Nodos

### Listar Nodos

```http
GET /nodes/
```

#### Ejemplo de Petición

```bash
curl "http://localhost:8000/nodes/"
```

#### Ejemplo de Respuesta

```json
{
  "nodes": [
    {
      "node_id": "node-001",
      "name": "Oficina Principal",
      "ip_address": "192.168.1.100",
      "port": 5001,
      "status": "online",
      "shared_files_count": 150,
      "last_seen": "2024-01-15T11:00:00Z"
    },
    {
      "node_id": "node-002",
      "name": "Oficina Secundaria",
      "ip_address": "192.168.1.101",
      "port": 5002,
      "status": "online",
      "shared_files_count": 200,
      "last_seen": "2024-01-15T11:00:05Z"
    }
  ],
  "total": 2,
  "online": 2,
  "offline": 0
}
```

### Registrar Nodo

```http
POST /register/
```

#### Body

```json
{
  "node_id": "node-003",
  "name": "Nueva Oficina",
  "ip_address": "192.168.1.102",
  "port": 5003
}
```

#### Ejemplo de Petición

```bash
curl -X POST "http://localhost:8000/register/" \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "node-003",
    "name": "Nueva Oficina",
    "ip_address": "192.168.1.102",
    "port": 5003
  }'
```

#### Ejemplo de Respuesta

```json
{
  "message": "Nodo registrado exitosamente",
  "node": {
    "node_id": "node-003",
    "name": "Nueva Oficina",
    "ip_address": "192.168.1.102",
    "port": 5003,
    "status": "online",
    "shared_files_count": 0,
    "last_seen": "2024-01-15T11:05:00Z"
  }
}
```

#### Códigos de Estado

| Código | Descripción |
|--------|-------------|
| `201` | Nodo registrado |
| `400` | Datos inválidos |
| `409` | Nodo ya existe |

### Registrar Archivos de un Nodo

```http
POST /register/files
```

#### Body

```json
{
  "node_id": "node-001",
  "files": [
    {
      "file_id": "abc123",
      "name": "documento.pdf",
      "path": "/documents/documento.pdf",
      "size": 1048576,
      "file_type": "pdf",
      "checksum": "sha256:abcdef...",
      "modified_at": "2024-01-15T10:00:00Z"
    }
  ]
}
```

#### Ejemplo de Respuesta

```json
{
  "message": "150 archivos registrados",
  "indexed_count": 150,
  "updated_count": 20,
  "errors": []
}
```

### Obtener Información de un Nodo

```http
GET /nodes/{node_id}
```

#### Ejemplo de Petición

```bash
curl "http://localhost:8000/nodes/node-001"
```

#### Ejemplo de Respuesta

```json
{
  "node_id": "node-001",
  "name": "Oficina Principal",
  "ip_address": "192.168.1.100",
  "port": 5001,
  "status": "online",
  "shared_files_count": 150,
  "total_size_bytes": 157286400,
  "last_seen": "2024-01-15T11:00:00Z",
  "created_at": "2024-01-10T08:00:00Z",
  "health": {
    "cpu_percent": 25.5,
    "memory_percent": 45.2,
    "disk_percent": 60.0
  }
}
```

### Eliminar Nodo

```http
DELETE /nodes/{node_id}
```

#### Ejemplo de Petición

```bash
curl -X DELETE "http://localhost:8000/nodes/node-003"
```

#### Ejemplo de Respuesta

```json
{
  "message": "Nodo eliminado exitosamente",
  "files_deleted": 50
}
```

#### Códigos de Estado

| Código | Descripción |
|--------|-------------|
| `200` | Nodo eliminado |
| `404` | Nodo no encontrado |

---

## 🏢 Modo Central

### Subir Archivo al Repositorio Central

```http
POST /central/upload
```

#### Form Data

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `file` | File | Archivo a subir |
| `folder` | string | Carpeta destino (opcional) |

#### Ejemplo de Petición

```bash
curl -X POST "http://localhost:8000/central/upload" \
  -F "file=@documento.pdf" \
  -F "folder=documentos/2024"
```

#### Ejemplo de Respuesta

```json
{
  "message": "Archivo subido exitosamente",
  "file": {
    "file_id": "central-abc123",
    "name": "documento.pdf",
    "size": 1048576,
    "path": "documentos/2024/documento.pdf",
    "checksum": "sha256:abcdef...",
    "uploaded_at": "2024-01-15T11:10:00Z"
  }
}
```

### Listar Archivos del Repositorio Central

```http
GET /central/files
```

#### Ejemplo de Petición

```bash
curl "http://localhost:8000/central/files"
```

#### Ejemplo de Respuesta

```json
{
  "files": [
    {
      "file_id": "central-001",
      "name": "documento.pdf",
      "size": 1048576,
      "path": "documentos/documento.pdf",
      "uploaded_at": "2024-01-15T10:00:00Z"
    }
  ],
  "total": 25,
  "total_size_bytes": 52428800
}
```

---

## 📊 Estadísticas

### Obtener Estadísticas del Sistema

```http
GET /stats/
```

#### Ejemplo de Petición

```bash
curl "http://localhost:8000/stats/"
```

#### Ejemplo de Respuesta

```json
{
  "nodes": {
    "total": 5,
    "online": 4,
    "offline": 1
  },
  "files": {
    "total": 1250,
    "total_size_bytes": 5242880000,
    "by_type": {
      "pdf": 450,
      "docx": 350,
      "xlsx": 200,
      "txt": 150,
      "other": 100
    }
  },
  "searches": {
    "total_today": 120,
    "avg_response_time_ms": 180,
    "success_rate": 0.98
  },
  "system": {
    "uptime_seconds": 86400,
    "version": "1.0.0",
    "mode": "distributed"
  }
}
```

---

## 🔧 Sistema

### Health Check

```http
GET /health
```

#### Ejemplo de Respuesta

```json
{
  "status": "ok",
  "timestamp": "2024-01-15T11:15:00Z",
  "version": "1.0.0"
}
```

### Información del Sistema

```http
GET /info
```

#### Ejemplo de Respuesta

```json
{
  "app_name": "DistriSearch",
  "version": "1.0.0",
  "mode": "distributed",
  "features": {
    "central_mode": false,
    "replication": false,
    "authentication": false
  },
  "database": {
    "type": "sqlite",
    "size_bytes": 10485760
  }
}
```

---

## 🔐 Autenticación

Si la autenticación está habilitada, incluye el API key en el header:

```bash
curl "http://localhost:8000/search/?q=documento" \
  -H "X-API-Key: your-api-key-here"
```

### Obtener Token (Futuro)

```http
POST /auth/token
```

#### Body

```json
{
  "username": "admin",
  "password": "password"
}
```

#### Respuesta

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

## 📝 Modelos de Datos

### Node

```json
{
  "node_id": "string",
  "name": "string",
  "ip_address": "string (IPv4)",
  "port": "integer (1-65535)",
  "status": "enum (online, offline, error)",
  "shared_files_count": "integer",
  "last_seen": "datetime (ISO 8601)"
}
```

### File

```json
{
  "file_id": "string (UUID)",
  "node_id": "string",
  "name": "string",
  "path": "string",
  "size": "integer (bytes)",
  "file_type": "string",
  "checksum": "string",
  "indexed_at": "datetime",
  "modified_at": "datetime",
  "metadata": "object (optional)"
}
```

### SearchResult

```json
{
  "file_id": "string",
  "name": "string",
  "path": "string",
  "size": "integer",
  "file_type": "string",
  "score": "float (0-10)",
  "node_id": "string",
  "node_name": "string",
  "indexed_at": "datetime",
  "modified_at": "datetime"
}
```

---

## 🚨 Códigos de Error

| Código | Descripción | Ejemplo |
|--------|-------------|---------|
| `400` | Bad Request | Parámetros inválidos |
| `401` | Unauthorized | API key inválida |
| `403` | Forbidden | Sin permisos |
| `404` | Not Found | Recurso no existe |
| `409` | Conflict | Recurso ya existe |
| `500` | Internal Server Error | Error del servidor |
| `503` | Service Unavailable | Nodo offline |

### Formato de Error

```json
{
  "error": {
    "code": "FILE_NOT_FOUND",
    "message": "El archivo solicitado no existe",
    "details": {
      "file_id": "abc123"
    }
  }
}
```

---

## 🔗 Rate Limiting

Las APIs tienen límites de tasa para prevenir abuso:

```http
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1642245600

{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Límite de peticiones excedido. Intenta en 60 segundos."
  }
}
```

---

## 📚 SDKs y Clientes

### Python

```python
import requests

class DistriSearchClient:
    def __init__(self, base_url="http://localhost:8000", api_key=None):
        self.base_url = base_url
        self.headers = {"X-API-Key": api_key} if api_key else {}
    
    def search(self, query, max_results=50):
        response = requests.get(
            f"{self.base_url}/search/",
            params={"q": query, "max_results": max_results},
            headers=self.headers
        )
        return response.json()
    
    def get_nodes(self):
        response = requests.get(
            f"{self.base_url}/nodes/",
            headers=self.headers
        )
        return response.json()
    
    def download_file(self, file_id, output_path):
        response = requests.get(
            f"{self.base_url}/download/{file_id}",
            headers=self.headers,
            stream=True
        )
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

# Uso
client = DistriSearchClient(api_key="your-key")
results = client.search("proyecto")
print(f"Encontrados {len(results['files'])} archivos")
```

---

[:octicons-arrow-left-24: Volver a Introducción](../introduccion.md){ .md-button }
[:octicons-arrow-right-24: Ver Ejemplos](../tutorials/index.md){ .md-button .md-button--primary }
