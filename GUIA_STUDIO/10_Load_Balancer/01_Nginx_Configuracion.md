# Configuración de Nginx

## Resolución dinámica
```nginx
resolver 127.0.0.11 valid=10s ipv6=off;
resolver_timeout 5s;
```
Usa el DNS interno de Docker; re-resuelve cada 10 s para detectar nuevos slaves.

## Upstreams
```nginx
upstream master_api {
    server master:8001 max_fails=3 fail_timeout=30s;
    keepalive 16;
}
```
Se incluyen archivos dinámicos desde `/etc/nginx/conf.d/upstreams/` generados por scripts.

## Proxy settings principales
```nginx
location /api/ {
    proxy_pass http://$slave_api_backend;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_next_upstream error timeout http_502 http_503 http_504;
    proxy_next_upstream_tries 3;
}
```
- `proxy_next_upstream` reintenta en otro backend si falla.
- Headers X-Real-IP y X-Forwarded-For preservan IP del cliente.

## Optimizaciones
- `worker_connections 4096`, `epoll`, `multi_accept`.
- Gzip para JSON, JS, CSS.
- `client_max_body_size 100M` (500 M para uploads).