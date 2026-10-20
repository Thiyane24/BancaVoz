FROM alpine:3.20 AS tailwind
WORKDIR /build
RUN apk add --no-cache curl
RUN curl -L --fail --silent --show-error \
    -o /usr/local/bin/tailwindcss \
    https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-linux-x64 \
    && chmod +x /usr/local/bin/tailwindcss
COPY tailwind.config.js ./
COPY bancavoz/web ./bancavoz/web
RUN tailwindcss -c tailwind.config.js \
    -i bancavoz/web/static/tailwind.input.css \
    -o bancavoz/web/static/tailwind.css --minify

FROM python:3.12-slim
WORKDIR /app
COPY . .
COPY --from=tailwind /build/bancavoz/web/static/tailwind.css bancavoz/web/static/tailwind.css
RUN pip install --no-cache-dir . \
    && useradd --create-home --shell /usr/sbin/nologin bancavoz \
    && chown -R bancavoz:bancavoz /app
USER bancavoz
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"
CMD ["sh", "-c", "bancavoz-migrate && exec uvicorn bancavoz.api:app --host 0.0.0.0 --port 8000"]
