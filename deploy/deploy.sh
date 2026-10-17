#!/usr/bin/env bash
# Deploys the latest Main: pull, install pinned deps, restart services, then check they stay up.
# Run by GitHub Actions over SSH (as the deploy key's forced command) or by hand on the server.
set -euo pipefail

UNITS=(craigbot-celery craigbot)

main() {
    local app_dir
    app_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    cd "$app_dir"

    if [[ "${1:-}" != "--pulled" ]]; then
        echo "==> Pulling latest code"
        git pull --ff-only
        # Continue with the freshly pulled copy of this script
        exec bash "$app_dir/deploy/deploy.sh" --pulled
    fi

    echo "==> Installing dependencies"
    venv/bin/pip install --quiet --disable-pip-version-check -r requirements.txt

    echo "==> Restarting services"
    sudo systemctl restart craigbot-celery craigbot

    # With Restart=always a crashing unit flickers back to "active", so also require a stable PID
    echo "==> Checking services stay up"
    sleep 5
    local -A first_pid
    local unit
    for unit in "${UNITS[@]}"; do
        first_pid[$unit]="$(systemctl show -p MainPID --value "$unit")"
    done
    sleep 15

    local failed=0 pid
    for unit in "${UNITS[@]}"; do
        pid="$(systemctl show -p MainPID --value "$unit")"
        if systemctl is-active --quiet "$unit" && [[ "$pid" != "0" && "$pid" == "${first_pid[$unit]}" ]]; then
            echo "    $unit: healthy (pid $pid)"
        else
            echo "    $unit: UNHEALTHY (pid ${first_pid[$unit]} -> $pid)"
            journalctl -u "$unit" -n 50 --no-pager || true
            failed=1
        fi
    done
    return "$failed"
}

main "$@"
