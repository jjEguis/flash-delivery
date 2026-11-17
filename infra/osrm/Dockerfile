FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends osmium-tool curl ca-certificates python3 && rm -rf /var/lib/apt/lists/*
COPY prepare.py /prepare.py
ENTRYPOINT ["python3", "/prepare.py"]
