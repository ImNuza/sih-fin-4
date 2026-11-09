# Image for the hosted dashboard. It has no API key, so the Live tab is off. See deploy/README.md.
FROM ghcr.io/astral-sh/uv:0.11.26 AS uv

FROM python:3.12.16-slim-trixie
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /srv/app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app/ app/
COPY scripts/dgs.py scripts/
COPY data/ data/

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin dashboard
USER 10001
ENV PATH=/opt/venv/bin:$PATH \
    HOME=/tmp \
    SIH_LIVE_DATA=off \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_FILE_WATCHER_TYPE=none \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD \
    ["python", "-c", \
     "import urllib.request as u; u.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=4)"]
CMD ["streamlit", "run", "app/app.py"]
