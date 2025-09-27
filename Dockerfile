FROM python:3.13-slim

RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN pip install poetry==2.2.0

WORKDIR /app

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VENV_IN_PROJECT=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache \
    POETRY_VENV_CREATE=false

COPY pyproject.toml poetry.lock* ./

RUN poetry install --only=main --no-root && rm -rf $POETRY_CACHE_DIR

COPY . .

RUN poetry install --only-root

CMD ["python", "main.py"]