# Tests, systemd Service & CI/CD — Design

Date: 2026-10-17
Status: Approved in conversation, awaiting written-spec review

## Goal

CraigBot currently has no tests and is deployed by SSHing into the server and killing
the bot process running inside `screen`, at which point `run.sh` loops: `git pull`,
`pip-review --auto` (upgrades every package, ignoring pins), restart Celery, relaunch.

After this work:

1. A pytest suite covers pure logic, real-Postgres database behaviour, cog commands,
   and an import/load smoke test.
2. The bot and Celery worker run as systemd services (auto-restart, start on boot,
   journald logs) instead of `screen` + `run.sh`.
3. Every push/PR runs lint + tests on GitHub Actions; pushes to `Main` that pass are
   deployed automatically over SSH, with a post-restart health check.

Success = pushing to `Main` results in the new code running on the server with no
manual steps, and a broken commit (failing tests or failing to start) turns the
GitHub run red instead of silently taking the bot down.

## Environment facts

- Server: Ubuntu 24.04 (kernel 6.8), x86_64, Python 3.12.3, reachable by SSH from
  GitHub-hosted runners.
- Postgres and Redis run on the server at `localhost`.
- Bot lives in a git checkout on the server with a `venv/`; config in `prod.env`.
- Primary branch: `Main`.

## 1. Service layer (server)

New directory `deploy/`:

- `deploy/craigbot-celery.service` — runs `venv/bin/celery -A audio.tasks worker
  --concurrency=1` from the checkout directory as the bot's user.
  `Restart=on-failure`, `WantedBy=multi-user.target`.
- `deploy/craigbot.service` — runs `venv/bin/python app.py`. `Wants=` and `After=`
  `craigbot-celery.service`, `postgresql.service`, `redis-server.service`,
  `network-online.target`. `Restart=on-failure`, `RestartSec=5`. Output to journald.
- Unit files use placeholder user/path values that `deploy/README.md` instructs the
  user to edit (or are templated by a small install step in the README); they are
  copied to `/etc/systemd/system/` once.
- `deploy/deploy.sh` (run on the server by CI, also runnable by hand):
  1. `cd` to the checkout (script's own repo root).
  2. `git pull --ff-only` — fails loudly if the server checkout has diverged rather
     than overwriting local changes.
  3. `venv/bin/pip install -r requirements.txt` (pinned; replaces `pip-review --auto`).
  4. `sudo systemctl restart craigbot-celery craigbot`.
  5. Wait ~15s, then `systemctl is-active` both units. If either is not active, print
     the last ~50 journal lines for it and exit non-zero.
  - `set -euo pipefail` throughout.
- Sudoers drop-in (documented in README, not installed automatically) allowing the
  deploy user to run only `systemctl restart craigbot craigbot-celery` /
  `systemctl restart craigbot-celery craigbot` and `systemctl is-active` on those
  units, plus `journalctl -u` for them, without a password.
- `deploy/README.md` — one-time setup: install units, `daemon-reload`, `enable`,
  generate a dedicated deploy SSH keypair and add the public key to
  `authorized_keys`, add the sudoers rule, capture `ssh-keyscan` output for the
  known-hosts secret, add GitHub secrets/environment, stop the old `screen` session,
  start the services, verify with `journalctl -u craigbot -f`.
- `run.sh` is deleted. README.md "Usage" section updated to describe systemd and the
  deploy flow.

Explicitly out of scope: automatic rollback, Docker, untracking `cookies.txt`
(noted as a follow-up: if the server ever modifies `cookies.txt`, `--ff-only` will
refuse to pull; the robust fix is to stop tracking it).

## 2. Testing

### Tooling

- `requirements-dev.txt`: `-r requirements.txt` plus `pytest`, `pytest-asyncio`,
  `ruff` (pinned versions). Server installs only `requirements.txt`.
- `pyproject.toml`: pytest config (`testpaths = ["tests"]`, `asyncio_mode = "auto"`)
  and ruff config (`select = ["F"]` — pyflakes only; exclude `venv`).
- `docker-compose.test.yml`: a single `postgres:16` service on port 5432 with
  user/password/db `craig_test`, for local runs.

### Testability changes (production behaviour unchanged)

- `database/database.py`: build the URL from `DB_HOST` (default `localhost`) and
  `DB_PORT` (default `5432`) in addition to existing vars; if `DATABASE_URL` is set,
  use it (with the driver swapped to `asyncpg` / `psycopg2` as appropriate for
  `async_`).
- `craig.py`: replace the module-level `Session = async_sessionmaker(... get_engine())`
  with a lazily created sessionmaker (created on first use of `bot.session`), so
  importing `craig` does not create an engine.
- `audio/tasks.py`: same lazy treatment for the sync `Session`; Redis broker/backend
  URL built from optional `REDIS_URL` (default `redis://localhost:6379`) with the
  existing db-number logic preserved.
- Any other import-time side effects discovered while writing the smoke test get the
  same minimal lazy-init treatment.

### Test layers (`tests/`)

1. **Unit (no DB):**
   - `audio/audio.py`: `extract_youtube_reference_from_url` (watch?v=, /video/,
     youtu.be, non-YouTube → None), `extract_youtube_playlist_reference`,
     `ensure_youtube_reference` with `YoutubeSearch` mocked (URL passthrough, search
     hit, search miss).
   - `database/audio.py`: `Song.link`, `full_filename`, `full_normalized_filename`,
     `info`, `__str__`; `find_yt_dlp_file` using `tmp_path` (finished file preferred,
     `.part` fallback, none → None); `Guild.is_playing`.
   - `utils/embedded_messages.py`: `human_numbers`, `now_playing`, `queue`,
     `magic_8_ball` produce embeds with expected fields.
2. **Database (real Postgres):** `conftest.py` reads `DATABASE_URL`; if unset or
   unreachable, DB-marked tests skip with a clear reason. Creates schema once per
   session (`Base.metadata.create_all`), and gives each test an `AsyncSession` bound
   to a connection inside a transaction that is rolled back afterwards.
   - `Song.get_by_reference` (hit/miss), `Song.get_random` (only downloaded songs with
     null/empty `download_error`; None when none qualify), `Guild.ensure_guild`
     (creates once, returns existing), `Guild.add_song_to_queue`, `Favourite`
     relationship round-trip, `Tag` CRUD.
3. **Cog tests:** a fake bot whose `session` property returns the test session, and
   a fake `ctx` (`AsyncMock` `send`, guild/author ids). Invoke command callbacks
   directly (`cog.tag_add.callback(cog, ctx, ...)`).
   - `TagCog`: add, duplicate add, delete, delete missing, list, `on_message` lookup
     (hit, miss, bot author ignored, DM ignored).
   - Selected `AudioCog` / `FunCog` / `AdminCog` paths that do not require voice
     connections; Celery `.delay` and yt-dlp calls mocked.
4. **Smoke:** every module under `cogs/`, `audio/`, `database/`, `utils/` plus
   `craig.py` and `quotes.py` imports without error; each cog's `setup()` adds its cog
   to a minimal `commands.Bot` (DB/Celery/network calls patched).

Never contacted from tests: Discord gateway/API, YouTube/yt-dlp network, Redis/Celery.

Existing bugs the tests surface (e.g. `ensure_youtube_reference` constructs but never
raises `DownloadError` on a search miss, leading to `IndexError`) are fixed in scope
when the fix is a one-liner; anything larger is marked `xfail` with a reason and
listed in the final summary.

No coverage threshold is enforced.

## 3. CI/CD (`.github/workflows/ci.yml`)

- Triggers: `push` (all branches), `pull_request`.
- **`test` job** (`ubuntu-latest`):
  - Service container `postgres:16` (user/password/db `craig_test`, health-checked).
  - `actions/setup-python` with Python `3.12` and pip cache.
  - `apt-get install ffmpeg` only if an import requires it.
  - `pip install -r requirements-dev.txt`.
  - `ruff check .`
  - `pytest` with `DATABASE_URL=postgresql://craig_test:craig_test@localhost:5432/craig_test`.
- **`deploy` job:**
  - `needs: test`; `if: github.event_name == 'push' && github.ref == 'refs/heads/Main'`.
  - `environment: production`; `concurrency: { group: production, cancel-in-progress: false }`.
  - Writes `DEPLOY_SSH_KEY` to a temp key file (0600) and `DEPLOY_KNOWN_HOSTS` to a
    known_hosts file; runs plain `ssh` (no third-party action) with
    `StrictHostKeyChecking=yes`:
    `ssh -p "${DEPLOY_PORT:-22}" "$DEPLOY_USER@$DEPLOY_HOST" "$DEPLOY_PATH/deploy/deploy.sh"`.
  - Job status mirrors `deploy.sh` exit code.
- Secrets (in the `production` environment): `DEPLOY_HOST`, `DEPLOY_USER`,
  `DEPLOY_SSH_KEY`, `DEPLOY_KNOWN_HOSTS`, `DEPLOY_PATH`; optional `DEPLOY_PORT`.
- Failure notification: GitHub's default workflow-failure email. Existing
  `last_error.txt` → owner DM behaviour is unchanged.

## Rollout order

1. Land testability refactors, tests, lint config, workflow, `deploy/` files on a
   feature branch; CI test job green.
2. Merge to `Main`. The deploy job fails until secrets exist — expected.
3. User follows `deploy/README.md` on the server, adds secrets, stops `screen`,
   starts services.
4. Re-run the deploy job (or push a trivial commit) and confirm a green automated
   deploy.
5. `run.sh` removal is part of step 1's changes; it is no longer used after step 3.
