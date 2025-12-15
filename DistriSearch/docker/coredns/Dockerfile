FROM coredns/coredns:1.11.1

# Copy CoreDNS configuration
COPY Corefile /etc/coredns/Corefile
COPY zones/ /etc/coredns/zones/

EXPOSE 53 53/udp

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD dig @localhost distrisearch.local +short || exit 1

ENTRYPOINT ["/coredns"]
CMD ["-conf", "/etc/coredns/Corefile"]
