# Deploying CraigBot

Pushes to `Main` run the test suite on GitHub Actions. If it passes, the `deploy` job SSHes into the
server, and the deploy key's forced command runs `deploy/deploy.sh` with the tested commit's SHA.
That script:

1. Fast-forwards the checkout to exactly that commit (never a newer, untested one). Run by hand
   with no SHA, it does `git pull --ff-only` instead.
2. `venv/bin/pip install -r requirements.txt`
3. `sudo systemctl restart craigbot-celery craigbot`
4. Waits ~20s and checks that both services are active with a stable PID. If not, it prints their
   recent logs and fails the GitHub run.

The bot (`craigbot.service`) and Celery worker (`craigbot-celery.service`) run under systemd. They
restart automatically, including after `!restart`, start on boot, and log to the journal. The Celery
unit upgrades `yt-dlp` each time it starts, so YouTube changes don't break downloads.

## One-time server setup

Run these on the server as the user that owns the bot checkout (the one that currently runs `screen`).

1. **Get the deploy files:** `cd ~/CraigBot && git pull`
2. **Install the services:** `sudo deploy/install-services.sh`
   This writes the units to `/etc/systemd/system/` with your user and path filled in, adds a sudoers
   rule allowing only `systemctl restart craigbot-celery craigbot`, adds you to `systemd-journal`,
   and enables both units at boot.
3. **Stop the old setup:**
   ```bash
   screen -ls                      # find the session running run.sh
   screen -S <session> -X quit     # stops run.sh and the bot
   pkill -f 'celery -A audio.tasks worker' || true
   pgrep -af 'celery -A audio.tasks worker'   # must print nothing; old workers would run stale code
   ```
4. **Start the services:**
   ```bash
   sudo systemctl start craigbot-celery craigbot
   systemctl status craigbot craigbot-celery
   journalctl -u craigbot -f       # Ctrl+C to stop following
   ```

## Deploy key (GitHub Actions → server)

1. On your own machine, create a key used only for deploys:
   ```bash
   ssh-keygen -t ed25519 -f craigbot_deploy -N "" -C github-actions-deploy
   ```
2. On the server, add the **public** key (`craigbot_deploy.pub`) to `~/.ssh/authorized_keys` on one
   line, restricted so it can only run the deploy script (use your real checkout path):
   ```text
   command="/home/<user>/CraigBot/deploy/deploy.sh",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty ssh-ed25519 AAAA... github-actions-deploy
   ```
3. Capture the server's host key so GitHub can verify it's talking to your server:
   ```bash
   ssh-keyscan -p 22 your.server.example
   ```
   Compare the fingerprint with `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` on the server.
4. Test it from your machine: `ssh -i craigbot_deploy <user>@your.server.example`. It should run a
   deploy and finish with `healthy` for both services.

## GitHub configuration

In the repo: **Settings → Environments → New environment → `production`**. Optionally limit it to
the `Main` branch. Add these environment secrets:

| Secret | Value |
|---|---|
| `DEPLOY_HOST` | Server hostname or IP |
| `DEPLOY_USER` | The bot's user on the server |
| `DEPLOY_PORT` | SSH port (optional, defaults to 22) |
| `DEPLOY_SSH_KEY` | Contents of the **private** key file `craigbot_deploy` |
| `DEPLOY_KNOWN_HOSTS` | Output of the `ssh-keyscan` command |

Or with the GitHub CLI: `gh secret set DEPLOY_SSH_KEY --env production < craigbot_deploy`, and so on.

Then re-run the latest failed `CI` workflow (**Actions → CI → Re-run jobs**) or push a commit.

## Day to day

- **Logs:** `journalctl -u craigbot -f`, `journalctl -u craigbot-celery -f`
- **Restart:** `sudo systemctl restart craigbot-celery craigbot` (or `!restart` in Discord)
- **Deploy by hand:** `~/CraigBot/deploy/deploy.sh`
- **Roll back:** `git revert <sha>` and push to `Main`. The revert deploys like any other commit.
- **Deploy failed with "Your local changes ... would be overwritten":** the server checkout has local
  changes. This is usually `cookies.txt`, which yt-dlp rewrites, so it clashes with any commit that
  updates it. Check with `git status` on the server, then keep or discard the change
  (`git checkout -- cookies.txt`) and re-run the deploy. To stop this for good, untrack `cookies.txt`
  (`git rm --cached cookies.txt` and add it to `.gitignore`) and keep the file only on the server.
- **Deploy failed with "Not possible to fast-forward":** the server checkout has its own commits.
  Inspect them with `git log origin/Main..HEAD` on the server.
