# syntax=docker/dockerfile:1
FROM python:3.12.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/opt/venv/bin:$PATH"
WORKDIR /service

FROM base AS runtime-deps
COPY requirements.txt ./
RUN python -m venv /opt/venv && pip install --no-cache-dir -r requirements.txt

FROM runtime-deps AS test-deps
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

FROM base AS runtime
COPY --from=runtime-deps /opt/venv /opt/venv
RUN groupadd --gid 10001 service && useradd --uid 10001 --gid 10001 --create-home service
COPY app ./app
COPY alembic.ini logging.json ./
COPY migrations ./migrations
LABEL org.opencontainers.image.source="https://github.com/WhyNot-png/anime-data-engineering"
LABEL org.opencontainers.image.description="Educational FastAPI task manager with PostgreSQL"
USER 10001:10001
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-config logging.json"]

FROM runtime AS test
USER root
COPY --from=test-deps /opt/venv /opt/venv
RUN mkdir /workspace && chown 10001:10001 /workspace
WORKDIR /workspace
COPY --chown=10001:10001 app ./app
COPY --chown=10001:10001 tests ./tests
COPY --chown=10001:10001 migrations ./migrations
COPY --chown=10001:10001 alembic.ini pyproject.toml pytest.ini ./
USER 10001:10001
CMD ["sh", "-c", "alembic upgrade head && python -m pytest"]
