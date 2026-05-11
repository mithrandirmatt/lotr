FROM python:3.11-slim AS build
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir fastapi uvicorn

FROM python:3.11-slim
WORKDIR /app
COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY . /app
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["uvicorn", "server.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
