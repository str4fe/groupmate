FROM node:22-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.12-slim AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY pyproject.toml ./
COPY app ./app
RUN pip install --prefix=/install .

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/usr/local/bin:$PATH"
RUN groupadd --system app && useradd --system --gid app --create-home app
WORKDIR /app
COPY --from=builder /install /usr/local
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
COPY --from=frontend-builder /frontend/dist ./frontend/dist
RUN mkdir -p /app/data && chown -R app:app /app
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
