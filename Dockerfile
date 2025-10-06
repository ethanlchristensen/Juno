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

RUN apt-get update && apt-get install -y curl xz-utils libopus0 ca-certificates libnss3 libssl3 && rm -rf /var/lib/apt/lists/*


RUN curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz -o ffmpeg.tar.xz \
    && tar -xf ffmpeg.tar.xz \
    && cd ffmpeg-*-static \
    && mv ffmpeg ffprobe /usr/local/bin/ \
    && cd .. && rm -rf ffmpeg.tar.xz ffmpeg-*-static

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}
COPY . .

CMD ["python", "main.py"]
