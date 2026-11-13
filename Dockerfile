FROM node:22-bookworm-slim AS node
FROM python:3.12-slim-bookworm
COPY --from=node /usr/local/bin/node /usr/local/bin/node
WORKDIR /workspace
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JSII_RUNTIME_PACKAGE_CACHE=disabled
COPY backend/requirements.txt backend/requirements.txt
COPY backend/requirements-runtime.lock backend/requirements-runtime.lock
COPY infrastructure/cdk/requirements.txt infrastructure/cdk/requirements.txt
COPY requirements-dev.txt .
COPY requirements-dev.lock .
RUN python -m pip install --no-cache-dir -r requirements-dev.txt
CMD ["sleep", "infinity"]
