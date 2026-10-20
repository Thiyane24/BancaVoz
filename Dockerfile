FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir . \
    && useradd --create-home --shell /usr/sbin/nologin bancavoz \
    && chown -R bancavoz:bancavoz /app
USER bancavoz
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"
CMD ["sh", "-c", "bancavoz-migrate && exec uvicorn bancavoz.api:app --host 0.0.0.0 --port 8000"]
