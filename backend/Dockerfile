# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --gid 10001 portal && \
    useradd --uid 10001 --gid portal --create-home --shell /usr/sbin/nologin portal

# Keep the application and dependency metadata together: this project uses a
# flat Python package, so package discovery needs app/ during installation.
COPY pyproject.toml ./
COPY app ./app

RUN python -m pip install --upgrade pip && \
    python -m pip install .

USER portal

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
