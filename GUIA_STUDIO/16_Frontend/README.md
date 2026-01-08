# Frontend de DistriSearch

El frontend es una SPA (Single Page Application) construida con **React**, **TypeScript** y **Vite**, estilizada con **Tailwind CSS**.

## Características
- Interfaz responsive para escritorio y móvil.
- Búsqueda en tiempo real con debounce.
- Subida de documentos con drag-and-drop.
- Dashboard de cluster con WebSocket.
- Autenticación JWT integrada.

## Estructura
```
frontend/src/
├── main.tsx          # Entry point
├── App.tsx           # Rutas principales
├── components/       # Componentes reutilizables
├── pages/            # Vistas (Home, Search, Upload, Dashboard)
├── services/         # Clientes API
├── hooks/            # Custom hooks
└── types/            # Definiciones TypeScript
```

## Build
```bash
npm install
npm run build   # genera dist/
```
El bundle se sirve desde Nginx en el contenedor slave.

Detalles en los siguientes archivos.