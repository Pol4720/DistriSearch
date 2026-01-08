# DistriSearch Load Balancer - Dynamic Discovery
# Nginx con descubrimiento dinámico de slaves

FROM nginx:1.25-alpine

# Install dependencies for dynamic upstream updates
RUN apk add --no-cache \
    curl \
    bash \
    python3 \
    supervisor

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Create directories
RUN mkdir -p /etc/nginx/conf.d/upstreams \
    && mkdir -p /etc/nginx/ssl \
    && mkdir -p /var/log/supervisor

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy upstream update script
COPY update-upstreams.sh /usr/local/bin/update-upstreams.sh
RUN chmod +x /usr/local/bin/update-upstreams.sh

# Create initial upstream config (includes master_api for HA mode)
RUN echo 'upstream slave_api { server 127.0.0.1:8000; }' > /etc/nginx/conf.d/upstreams/slaves.conf \
    && echo 'upstream slave_frontend { server 127.0.0.1:80; }' >> /etc/nginx/conf.d/upstreams/slaves.conf \
    && echo 'upstream master_api { server 127.0.0.1:8000; }' >> /etc/nginx/conf.d/upstreams/slaves.conf

# Copy supervisor configuration
COPY supervisord-lb.conf /etc/supervisor/conf.d/supervisord.conf

# Health check endpoint
RUN echo 'server { listen 80; location /health { return 200 "OK"; add_header Content-Type text/plain; } }' > /etc/nginx/conf.d/health.conf

EXPOSE 80 443

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
