FROM python:3.11-slim AS builder

WORKDIR /build

COPY pyproject.toml .
COPY src/ ./src/

RUN pip wheel --no-cache-dir . -w /wheels

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    docker-cli \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash sweuser

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl \
    && rm -rf /wheels \
    && find /usr/local -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

WORKDIR /app

USER sweuser

VOLUME ["/var/run/docker.sock"]

ENTRYPOINT ["swe-forge"]

CMD ["--help"]
