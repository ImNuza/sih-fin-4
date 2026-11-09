# Hosted dashboard

The team dashboard also runs on a small home server, behind a Cloudflare Tunnel. Ask Dewa for the link.

## How it works

- `Dockerfile` builds the app. The image holds the committed data only. It has no API key, so the Live tab is off (`SIH_LIVE_DATA=off`).
- `compose.yaml` runs two containers:
  - `dashboard`: Streamlit, on a network with no internet. Read-only filesystem, no Linux capabilities, non-root.
  - `tunnel`: cloudflared, the only way in. The server opens no inbound port.
- The server runs Docker in rootless mode under an unprivileged user.
- `pull-deploy.sh` runs every 5 minutes from a systemd timer (`systemd/`). When `main` changes, it pulls and rebuilds. A push to `main` is live within about 5 to 10 minutes.

## What this means for you

- Push to `main` as usual. Do not push secrets: the image would publish them.
- If the app fails to build, the old version keeps running. Tell Dewa.
- To change what runs on the server (compose, Dockerfile), open a PR and ask Dewa to review it.
