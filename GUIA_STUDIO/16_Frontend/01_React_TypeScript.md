# React y TypeScript

## Por qué React + TypeScript
- Componentes declarativos y reutilizables.
- Tipado estático reduce errores en tiempo de desarrollo.
- Ecosistema maduro (hooks, context, React Query).

## Configuración Vite
`vite.config.ts`:
```ts
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://localhost:8000' } }
})
```
Proxy local para desarrollo; en producción Nginx enruta `/api`.

## Tailwind CSS
`tailwind.config.js` define theme, colores y plugins. Clases utilitarias en JSX:
```tsx
<button className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded">
  Buscar
</button>
```

## Scripts
| Comando | Acción |
|---------|--------|
| `npm run dev` | Servidor desarrollo con HMR |
| `npm run build` | Build producción |
| `npm run preview` | Previsualizar build |