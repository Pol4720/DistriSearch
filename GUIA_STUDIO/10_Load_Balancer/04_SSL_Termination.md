# SSL/TLS Termination

## Terminación en load-balancer
Nginx maneja HTTPS y comunica con backends en HTTP interno; simplifica gestión de certificados.

## Configuración
```nginx
ssl_certificate /etc/nginx/ssl/server.crt;
ssl_certificate_key /etc/nginx/ssl/server.key;
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-...;
ssl_session_cache shared:SSL:50m;
```

## Generación de certificados (desarrollo)
`generate-ssl.sh`:
```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout server.key -out server.crt \
    -subj "/CN=distrisearch.local"
```
Para producción usar Let’s Encrypt o CA interna.

## Secrets en Swarm
```yaml
secrets:
  tls-cert:
    external: true
  tls-key:
    external: true
```
Crear con `docker secret create tls-cert server.crt` antes del deploy.

## Headers de seguridad
```nginx
add_header X-Frame-Options "SAMEORIGIN";
add_header X-Content-Type-Options "nosniff";
add_header X-XSS-Protection "1; mode=block";
```