#!/usr/bin/env bash
# One-time setup: installs the systemd units and the passwordless restart rule used by deploy.sh.
# Usage, from the checkout as the bot's user: sudo deploy/install-services.sh
set -euo pipefail

main() {
    if [[ $EUID -ne 0 || -z "${SUDO_USER:-}" ]]; then
        echo "Run this with sudo as the bot's user: sudo deploy/install-services.sh" >&2
        exit 1
    fi

    local app_dir user
    app_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    user="$SUDO_USER"

    echo "==> Installing systemd units for user $user in $app_dir"
    for unit in craigbot craigbot-celery; do
        sed -e "s|__USER__|$user|g" -e "s|__APP_DIR__|$app_dir|g" \
            "$app_dir/deploy/$unit.service" > "/etc/systemd/system/$unit.service"
    done

    echo "==> Allowing $user to restart the services without a password"
    local sudoers_tmp
    sudoers_tmp="$(mktemp)"
    echo "$user ALL=(root) NOPASSWD: /usr/bin/systemctl restart craigbot-celery craigbot" > "$sudoers_tmp"
    visudo -cf "$sudoers_tmp"
    install -m 0440 "$sudoers_tmp" /etc/sudoers.d/craigbot-deploy
    rm -f "$sudoers_tmp"

    echo "==> Letting $user read the services' logs"
    usermod -aG systemd-journal "$user"

    systemctl daemon-reload
    systemctl enable craigbot-celery craigbot
    echo "Done. Stop the old screen session, then run: sudo systemctl start craigbot-celery craigbot"
}

main "$@"
