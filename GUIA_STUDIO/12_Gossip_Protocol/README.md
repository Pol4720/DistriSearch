# Protocolo Gossip en DistriSearch

Gossip (o epidemic protocol) propaga información de forma descentralizada: cada nodo intercambia datos con peers aleatorios hasta que todos convergen.

## Dónde se usa
- **UserDocumentRegistry**: sincroniza mapeo usuario→documentos entre nodos.
- Potencialmente: health status, estadísticas de carga.

## Características
| Aspecto | Valor |
|---------|-------|
| Consistencia | Eventual |
| Tolerancia a fallos | Alta (sin coordinador central) |
| Latencia de propagación | O(log N) rondas para N nodos |
| Overhead | Bajo (mensajes pequeños, periódicos) |

## Flujo básico
1. Nodo A selecciona peer aleatorio B.
2. A envía resumen (vector clocks) de sus entradas.
3. B responde con diferencias.
4. Ambos actualizan sus copias locales.
5. Repetir cada intervalo (ej. 5–30 s).

En los siguientes archivos se detalla la implementación.