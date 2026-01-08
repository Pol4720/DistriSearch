# Rolling updates y rollbacks

## update_config
```yaml
update_config:
  parallelism: 1
  delay: 30s
  failure_action: rollback
  order: start-first  # o stop-first
```
| Campo | Significado |
|-------|-------------|
| parallelism | Cuántas tareas actualizar simultáneamente |
| delay | Espera entre lotes de tareas |
| failure_action | `pause`, `continue` o `rollback` si falla |
| order | `start-first` (inicia nueva antes de parar vieja) o `stop-first` |

`slave` usa `start-first` para mantener capacidad durante la transición; `master` y `mongodb` usan `stop-first` para evitar conflictos de estado.

## rollback_config
```yaml
rollback_config:
  parallelism: 1
  delay: 10s
```
Define cómo revertir si `failure_action: rollback` se dispara.

## restart_policy
```yaml
restart_policy:
  condition: on-failure
  delay: 5s
  max_attempts: 5
```
Reintenta contenedores fallidos hasta 5 veces antes de detenerse.

## Healthcheck y start_period
Los servicios definen `healthcheck` con `start_period` amplio (30–120 s) para permitir arranque sin falsas alarmas; si el check falla tras reintentos, Swarm reemplaza la tarea.

## Ejemplo de actualización
```bash
docker service update --image distrisearch/slave:v2 distrisearch_slave
```
Swarm aplica las reglas de `update_config` y, si todo es exitoso, finaliza sin corte de servicio.