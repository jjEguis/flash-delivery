FROM node:22-bookworm-slim AS node
FROM python:3.12-slim-bookworm
COPY --from=node /usr/local/bin/node /usr/local/bin/node
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JSII_RUNTIME_PACKAGE_CACHE=disabled
COPY app/requirements.txt app/requirements.lock ./
COPY app/layers/dependencias/requirements.txt app/layers/dependencias/requirements.lock layers/dependencias/
RUN python -m pip install --no-cache-dir -r requirements.txt
CMD ["sleep", "infinity"]
