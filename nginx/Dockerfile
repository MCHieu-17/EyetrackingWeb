FROM nginx:1.27.3-alpine

# Config thuần HTTP cho local (không TLS/Cloudflare).
COPY nginx.conf /etc/nginx/nginx.conf
COPY default.conf /etc/nginx/conf.d/default.conf

# Thư mục cache asset Next.js (proxy_cache_path trong default.conf).
RUN mkdir -p /var/cache/nginx/next_static \
    && chown -R nginx:nginx /var/cache/nginx

EXPOSE 80

# Healthcheck đánh endpoint nội bộ (IPv4 127.0.0.1) không phụ thuộc upstream.
HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD wget -qO- http://127.0.0.1:80/nginx-health || exit 1
