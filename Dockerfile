FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m appuser

COPY pyproject.toml README.md ./
COPY product_app ./product_app
COPY docs ./docs
COPY tests ./tests

RUN python -m pip install --upgrade pip \
    && python -m pip install . \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["python", "-m", "product_app.webapp"]
