FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev

COPY . .
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "api_app:app", "--host", "0.0.0.0", "--port", "8000"]