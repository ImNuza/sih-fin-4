#!/usr/bin/env bash
# Pull main and rebuild the hosted dashboard when main changed. Pass --force to rebuild anyway.
#
# Runs on the server as the hosting user, from a systemd timer (deploy/systemd/).
# Install a copy outside the repo, so a pushed change cannot change the deploy script itself:
#   install -m 755 deploy/pull-deploy.sh ~/bin/sih-pull-deploy
set -euo pipefail

REPO_DIR=${REPO_DIR:-$HOME/sih-fin-4}
ENV_FILE=${ENV_FILE:-$HOME/secrets/sih-fin-4.env}

cd "$REPO_DIR"
git fetch --quiet origin main
if [[ $(git rev-parse HEAD) == $(git rev-parse origin/main) && ${1:-} != "--force" ]]; then
  exit 0
fi
git reset --quiet --hard origin/main
docker compose --env-file "$ENV_FILE" up --detach --build --remove-orphans
docker image prune --force >/dev/null
echo "Deployed $(git rev-parse --short HEAD)"
