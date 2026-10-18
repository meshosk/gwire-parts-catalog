FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY build_indexes.py /app/build_indexes.py

ENTRYPOINT ["python", "/app/build_indexes.py"]
CMD ["--root", "/catalog"]
