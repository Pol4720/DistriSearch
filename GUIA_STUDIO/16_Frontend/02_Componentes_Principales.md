# Componentes Principales

## Navbar
Barra superior con logo, búsqueda rápida y menú de usuario.

## SearchBar
Input con debounce (300 ms); dispara búsqueda al escribir.

## DocumentCard
Tarjeta que muestra título, fragmento, score y nodo origen.

## UploadDropzone
Zona drag-and-drop para subir archivos; muestra progreso.

## ClusterDashboard
Visualiza nodos, particiones y estado de salud; se actualiza vía WebSocket.

## AuthForms
- `LoginForm`: email + password.
- `RegisterForm`: registro de nuevo usuario.

## Páginas
| Ruta | Componente | Descripción |
|------|------------|-------------|
| / | Home | Landing con búsqueda |
| /search | SearchResults | Resultados paginados |
| /upload | UploadPage | Subir documentos |
| /dashboard | Dashboard | Admin cluster |
| /login | LoginPage | Autenticación |