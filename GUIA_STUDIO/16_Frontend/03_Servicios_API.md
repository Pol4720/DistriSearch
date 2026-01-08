# Servicios API

## Estructura
`services/api.ts` exporta funciones que llaman al backend:
```ts
export const searchDocuments = async (query: string): Promise<SearchResult[]> => {
  const res = await fetch(`/api/v1/search?q=${encodeURIComponent(query)}`, {
    headers: { Authorization: `Bearer ${getToken()}` }
  });
  return res.json();
};
```

## Servicios principales
| Servicio | Funciones |
|----------|----------|
| auth | login, register, logout, refreshToken |
| documents | upload, list, get, delete |
| search | searchDocuments |
| cluster | getNodes, getPartitions, rebalance |

## Manejo de errores
Interceptor global captura 401 y redirige a login; muestra toast en errores 4xx/5xx.

## WebSocket
```ts
const ws = new WebSocket('wss://host/ws/dashboard');
ws.onmessage = (e) => updateClusterState(JSON.parse(e.data));
```
Recibe eventos de nodos, particiones y alertas en tiempo real.

## Caché con React Query
Opcional: usar `useQuery` para cachear resultados de búsqueda y docs.