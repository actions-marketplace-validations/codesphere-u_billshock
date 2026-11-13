FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r billshock && useradd -r -g billshock -m billshock

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY skills/billshock/scripts/billshock.py skills/billshock/scripts/billshock.py

RUN pip install --no-cache-dir --no-deps .

USER billshock
WORKDIR /workspace

ENTRYPOINT ["billshock"]
CMD ["."]
