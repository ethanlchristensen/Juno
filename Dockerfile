FROM python:3.13-slim as builder

RUN pip install poetry==2.2.0

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

COPY pyproject.toml poetry.lock* ./
RUN touch README.md
RUN poetry install --only=main --no-root && rm -rf $POETRY_CACHE_DIR


# --- Runtime stage ---
FROM python:3.13-slim as runtime

# Add Debian testing repo for newer ffmpeg
RUN echo "deb http://deb.debian.org/debian testing main" > /etc/apt/sources.list.d/testing.list \
    && apt-get update \
    && apt-get install -y -t testing ffmpeg \
    && apt-get install -y curl xz-utils libopus0 ca-certificates libnss3 libssl3 \
    && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}
COPY . .

CMD ["python", "main.py"]