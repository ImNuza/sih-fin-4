# Image for the pricing API and admin panel. Logins and the database URL come from compose at run
# time, never from the image. See deploy/README.md. Build from the repo root.
FROM ghcr.io/astral-sh/uv:0.11.26 AS uv

FROM python:3.12.16-slim-trixie AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-default-groups --group api --no-install-project

FROM python:3.12.16-slim-trixie
COPY --from=build /opt/venv /opt/venv
WORKDIR /srv/app
COPY api/ api/
COPY scripts/dgs.py scripts/
COPY data/processed/site_hazard_readings.csv data/processed/map_static.json \
     data/processed/map_buildings.json data/processed/day_readings.csv.gz data/processed/

RUN useradd --uid 10002 --no-create-home --shell /usr/sbin/nologin pricing
USER 10002
ENV PATH=/opt/venv/bin:$PATH \
    HOME=/tmp
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD \
    ["python", "-c", \
     "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/options', timeout=4)"]
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
