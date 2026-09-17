# ---- stage 1: build the React bundle ----
FROM node:20-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY web/ ./
RUN npm run build

# ---- stage 2: python runtime, serves API + bundle ----
FROM python:3.12-slim
WORKDIR /srv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# app/ is copied before `pip install .` because pyproject declares
# packages = ["app"]; installing without it present fails package discovery.
COPY pyproject.toml ./
COPY app/ ./app/
RUN pip install --upgrade pip && pip install .

COPY --from=web /web/dist ./web/dist

# Railway injects $PORT; this default is for local runs.
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
