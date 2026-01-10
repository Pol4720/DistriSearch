FROM coredns/coredns:1.11.1

# La imagen base de CoreDNS usa scratch, necesitamos una imagen con shell
# Usamos alpine como base y copiamos el binario de CoreDNS
FROM alpine:3.19

# Instalar bind-tools para tener dig disponible (con reintentos para red inestable)
RUN apk update --no-cache || apk update --no-cache || apk update --no-cache && \
    apk add --no-cache bind-tools || apk add --no-cache bind-tools

# Copiar el binario de CoreDNS desde la imagen oficial
COPY --from=coredns/coredns:1.11.1 /coredns /coredns

# Copy CoreDNS configuration
COPY Corefile /etc/coredns/Corefile
COPY zones/ /etc/coredns/zones/

# Puerto 5353 para evitar conflicto con systemd-resolved en el host
EXPOSE 5353 5353/udp

# Healthcheck usando dig
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD dig @127.0.0.1 -p 5353 distrisearch.local +short +time=2 || exit 1

ENTRYPOINT ["/coredns"]
CMD ["-conf", "/etc/coredns/Corefile"]
