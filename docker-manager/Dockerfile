FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY server.py http_handler.py catalog.py storage.py build_indexes.py /app/
COPY static /app/static
EXPOSE 8080
CMD ["python", "/app/server.py", "--tags", "/catalog/tags.json", "--port", "8080"]
