# Autenticación

## Flujo JWT
1. `POST /api/v1/auth/login` con `username` y `password`.
2. Backend valida contra SQLite (usuarios replicados por Raft).
3. Devuelve `access_token` (JWT) con expiración.
4. Cliente incluye header `Authorization: Bearer <token>` en peticiones.

## Registro
`POST /api/v1/auth/register` crea usuario; se replica vía Raft a todos los nodos.

## Dependencia de seguridad
```python
async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserModel:
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    user = await user_repo.get_by_id(payload["sub"])
    if not user:
        raise HTTPException(401)
    return user
```

## Tokens y secrets
- `JWT_SECRET` se almacena como Docker secret.
- Expiración configurable (default 24 h).

## Autenticación durante particiones
Cada nodo tiene copia local de usuarios en SQLite; puede validar JWT sin conectar al líder Raft (modo AP).