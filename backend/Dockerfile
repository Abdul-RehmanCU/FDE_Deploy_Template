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
    /usr/local/bin/python -c "from importlib.metadata import version; assert version('msgpack') == '1.2.2'; assert version('setuptools') == '84.0.0'" && \
    UV_NO_CACHE=1 uv pip install --python /app/.venv/bin/python "msgpack==1.2.2" "setuptools==84.0.0" && \
    find /app/.venv -type d \( -name 'msgpack-1.1.2.dist-info' -o -name 'setuptools-70.3.0.dist-info' \) -exec rm -rf {} + && \
    test -z "$(find /app/.venv -type d \( -name 'msgpack-1.1.2.dist-info' -o -name 'setuptools-70.3.0.dist-info' \) -print -quit)" && \
    /app/.venv/bin/python -c "from importlib.metadata import version; assert version('msgpack') == '1.2.2'; assert version('setuptools') == '84.0.0'"

WORKDIR /app/backend/

RUN groupadd --gid 10001 app && \
    useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app && \
    mkdir -p /app/backend/.data/storage && \
    chown -R 10001:10001 /app

USER 10001:10001

EXPOSE 8000

CMD ["fastapi", "run", "app/main.py", "--port", "8000", "--workers", "1"]
