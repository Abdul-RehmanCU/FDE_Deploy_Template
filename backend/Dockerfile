FROM python:3.14-slim-trixie@sha256:caaf356f40667c496d405780745b9ac25771c189a51dfcc42430d531ea09f8a2

ENV PYTHONUNBUFFERED=1

# Install uv
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=ghcr.io/astral-sh/uv:0.9.26@sha256:9a23023be68b2ed09750ae636228e903a54a05ea56ed03a934d00fe9fbeded4b /uv /uvx /bin/

# Compile bytecode
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#compiling-bytecode
ENV UV_COMPILE_BYTECODE=1

# uv Cache
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#caching
ENV UV_LINK_MODE=copy

WORKDIR /app/

# Place executables in the environment at the front of the path
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#using-the-environment
ENV PATH="/app/.venv/bin:$PATH"

# Install dependencies
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-workspace --package app

COPY ./backend/scripts /app/backend/scripts

COPY ./backend/pyproject.toml ./backend/alembic.ini /app/backend/

COPY ./backend/app /app/backend/app

# Sync the project
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --package app

# Editable/build tooling leaves package metadata in the application environment.
# Keep those distributions on fixed versions and assert the exact scanned environment.
RUN UV_NO_CACHE=1 uv pip install --system "msgpack==1.2.2" "setuptools==84.0.0" && \
    /usr/local/bin/python -c "from importlib.metadata import version; from pathlib import Path; import msgpack, setuptools; assert version('msgpack') == '1.2.2'; assert version('setuptools') == '84.0.0'; assert Path(msgpack.__file__).is_relative_to('/usr/local'); assert Path(setuptools.__file__).is_relative_to('/usr/local')" && \
    UV_NO_CACHE=1 uv pip install --python /app/.venv/bin/python "msgpack==1.2.2" "setuptools==84.0.0" && \
    rm -rf /usr/local/lib/python3.14/site-packages/pip /usr/local/lib/python3.14/site-packages/pip-*.dist-info /usr/local/lib/python3.14/ensurepip && \
    find /usr/local /app -type d \( -name 'msgpack-1.1.2.dist-info' -o -name 'setuptools-70.3.0.dist-info' \) -exec rm -rf {} + && \
    find /usr/local /app -type f \( -name 'msgpack-1.1.2*.whl' -o -name 'setuptools-70.3.0*.whl' \) -delete && \
    test -z "$(find /usr/local /app \( -name 'msgpack-1.1.2*' -o -name 'setuptools-70.3.0*' \) -print -quit)" && \
    /app/.venv/bin/python -c "from importlib.metadata import version; from pathlib import Path; import msgpack, setuptools; assert version('msgpack') == '1.2.2'; assert version('setuptools') == '84.0.0'; assert Path(msgpack.__file__).is_relative_to('/app/.venv'); assert Path(setuptools.__file__).is_relative_to('/app/.venv')"

WORKDIR /app/backend/

RUN SECRET_KEY=build-only-secret-key-with-at-least-32-characters \
    DATABASE_URL=postgresql://app:build-password@127.0.0.1:5432/app \
    REDIS_URL=redis://127.0.0.1:6379/0 FASTAPI_ENV=test STORAGE_BACKEND=local \
    /app/.venv/bin/python -c "import alembic, app.main, app.outbox_publisher, app.worker"

RUN groupadd --gid 10001 app && \
    useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app && \
    mkdir -p /app/backend/.data/storage && \
    chown -R 10001:10001 /app

USER 10001:10001

EXPOSE 8000

CMD ["fastapi", "run", "app/main.py", "--port", "8000", "--workers", "1"]
