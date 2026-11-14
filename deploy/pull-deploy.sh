#!/usr/bin/env bash
# Pull main and rebuild the hosted dashboard when main changed. Pass --force to rebuild anyway.
#
# Runs on the server as the hosting user, from a systemd timer (deploy/systemd/).
# Install a copy outside the repo, so a pushed change cannot change the deploy script itself:
#   install -m 755 deploy/pull-deploy.sh ~/bin/sih-pull-deploy
set -euo pipefail

REPO_DIR=${REPO_DIR:-$HOME/sih-fin-4}
ENV_FILE=${ENV_FILE:-$HOME/secrets/sih-fin-4.env}
# The checkout moves before the build, so only this file says which commit is really running.
# A failed build leaves it unchanged, and the next run tries again.
DEPLOYED_FILE=${DEPLOYED_FILE:-$HOME/.local/state/sih-deployed-commit}

cd "$REPO_DIR"
git fetch --quiet origin main
target=$(git rev-parse origin/main)
deployed=$(cat "$DEPLOYED_FILE" 2>/dev/null || true)
if [[ $target == "$deployed" && ${1:-} != "--force" ]]; then
  exit 0
fi
git reset --quiet --hard "$target"
docker compose --env-file "$ENV_FILE" up --detach --build --remove-orphans
docker image prune --force >/dev/null
mkdir -p "$(dirname "$DEPLOYED_FILE")"
echo "$target" > "$DEPLOYED_FILE"
echo "Deployed $(git rev-parse --short HEAD)"
