#!/usr/bin/env bash
# Pull main and rebuild the hosted dashboard when main changed. Pass --force to rebuild anyway.
#
# Runs on the server as the hosting user, from a systemd timer (deploy/systemd/).
# Install a copy outside the repo, so a pushed change cannot change the deploy script itself:
#   install -m 755 deploy/pull-deploy.sh ~/bin/sih-pull-deploy
# With SIH_ALERT_TELEGRAM_TOKEN and SIH_ALERT_TELEGRAM_CHAT_ID in the env file, it sends one
# Telegram message when a commit fails to deploy and one when a deploy works again.
set -euo pipefail

REPO_DIR=${REPO_DIR:-$HOME/sih-fin-4}
ENV_FILE=${ENV_FILE:-$HOME/secrets/sih-fin-4.env}
STATE_DIR=${STATE_DIR:-$HOME/.local/state}
# The checkout moves before the build, so only this file says which commit is really running.
# A failed build leaves it unchanged, and the next run tries again.
DEPLOYED_FILE=$STATE_DIR/sih-deployed-commit
# The commit that last failed, so a retry every few minutes does not send the alert again.
FAILED_FILE=$STATE_DIR/sih-failed-commit
HEALTHY_WAIT_SECONDS=180

env_value() {
  grep -m1 "^$1=" "$ENV_FILE" | cut -d= -f2- || true
}

alert() {
  local token chat
  token=$(env_value SIH_ALERT_TELEGRAM_TOKEN)
  chat=$(env_value SIH_ALERT_TELEGRAM_CHAT_ID)
  [[ -n $token && -n $chat ]] || return 0
  curl --silent --show-error --max-time 15 --output /dev/null \
    "https://api.telegram.org/bot$token/sendMessage" \
    --data-urlencode "chat_id=$chat" --data-urlencode "text=$1" || true
}

commit_line() {
  git log -1 --format='%h by %an: %s' "$1"
}

cd "$REPO_DIR"
mkdir -p "$STATE_DIR"
git fetch --quiet origin main
target=$(git rev-parse origin/main)
deployed=$(cat "$DEPLOYED_FILE" 2>/dev/null || true)
if [[ $target == "$deployed" && ${1:-} != "--force" ]]; then
  exit 0
fi
git reset --quiet --hard "$target"
log=$(mktemp)
trap 'rm -f "$log"' EXIT
if ! docker compose --env-file "$ENV_FILE" up --detach --build --remove-orphans \
    --wait --wait-timeout "$HEALTHY_WAIT_SECONDS" 2>&1 | tee "$log"; then
  if [[ $(cat "$FAILED_FILE" 2>/dev/null || true) != "$target" ]]; then
    echo "$target" > "$FAILED_FILE"
    alert "SIH deploy FAILED for $(commit_line "$target")
$(grep -iE 'error|fail|unhealthy' "$log" | tail -3)
A failed build keeps the last good version. A container that did not start is down.
The server retries every 6 minutes."
  fi
  exit 1
fi
docker image prune --force >/dev/null
echo "$target" > "$DEPLOYED_FILE"
if [[ -f $FAILED_FILE ]]; then
  rm "$FAILED_FILE"
  alert "SIH deploy works again: $(commit_line "$target")"
fi
echo "Deployed $(git rev-parse --short HEAD)"
