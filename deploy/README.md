# Hosted dashboard and pricing API

The team dashboard and the pricing API also run on a small home server, behind a Cloudflare Tunnel. Ask Dewa for the link.

## How it works

- `Dockerfile` builds the app. The image holds the committed data only, with no API key. The Live tab is off by default (`SIH_LIVE_DATA=off`).
- `compose.yaml` runs two containers:
  - `dashboard`: Streamlit. Read-only filesystem, no Linux capabilities, non-root. Compose turns the Live tab on and gives it the data.gov.sg development key from a file on the server. It can reach the public internet only. The server firewall blocks the rest of the home network.
  - `api`: the pricing API and admin panel (`api/Dockerfile`). Same lock-down as the dashboard. It reaches the public internet only, for live NEA readings and the shop box's model (`XAI_API_KEY`, optional).
  - `db`: Postgres for the tariff versions the admin panel saves. Data is kept in the `tariff-db` volume. No internet.
  - `tunnel`: cloudflared, the only way in. The server opens no inbound port.
- The server runs Docker in rootless mode under an unprivileged user.
- `pull-deploy.sh` runs every 5 minutes from a systemd timer (`systemd/`). When `main` changes, it pulls and rebuilds. A push to `main` is live within about 5 to 10 minutes.

## What this means for you

- Push to `main` as usual. Do not push secrets: the image would publish them.
- If the app fails to build, the old version keeps running. Tell Dewa.
- To change what runs on the server (compose, Dockerfile), open a PR and ask Dewa to review it.

## Setting up the pricing API (Dewa, once)

1. Add three lines to `~/secrets/sih-fin-4.env` **before** the API is merged to `main`. Without them, compose refuses to start and the server keeps the old version.
   ```
   ADMIN_USERNAME=<admin login for the admin panel>
   ADMIN_PASSWORD=<output of: openssl rand -hex 16>
   POSTGRES_PASSWORD=<output of: openssl rand -hex 24>
   ```
   Use hex passwords: the Postgres one goes inside a database URL, where some symbols break it.
2. In the Cloudflare tunnel, add a public hostname for the API with the service `http://api:8000`. The admin panel is at `/admin/` on that hostname. Put it behind the same Access policy as the dashboard.
3. Back up the tariff database:
   ```
   docker compose exec db pg_dump --username=safeday safeday > tariff-backup.sql
   ```
