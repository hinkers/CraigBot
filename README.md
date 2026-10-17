# CraigBot
A Python-based bot to automate various tasks, he's lightweight, modular, and easy to configure.

## Table of Contents
- [What is it](#what-is-it)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Testing](#testing)
- [Project structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)

## What is it
CraigBot is a lightweight bot written in Python intended to automate repetitive or interactive tasks.  
It supports modular extensions and simple configuration through environment variables.

## Features
- Easily configured via `prod.env` / `dev.env` (see `example.env`)
- Modular design using Python cogs for additional functionality
- Quote feature (via `quotes.py`)
- Cookie/session support (`cookies.txt`)
- Runs as systemd services with automated, tested deploys (see `deploy/`)
- Dependency management via `requirements.txt`

## Prerequisites
Before you use this bot make sure you have:
- Python 3.12
- pip
- PostgreSQL and Redis
- Basic command-line familiarity
- API tokens or credentials for any connected services

## Installation
```bash
git clone https://github.com/hinkers/CraigBot.git
cd CraigBot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp example.env prod.env   # or dev.env, used when craig_debug=true
# Edit the env file with your configuration
```

## Configuration
The bot reads `prod.env`, or `dev.env` when the `craig_debug=true` environment variable is set.
See `example.env` for every setting:

- `BOT_TOKEN`: Discord bot token
- `DB_USERNAME`, `DB_PASSWORD`, `DB_DATABASE_NAME`: PostgreSQL credentials
- `DB_HOST` / `DB_PORT`: optional, default `localhost` / `5432`
- `DATABASE_URL`: optional full Postgres URL that replaces the `DB_*` settings
- `REDIS_URL`: optional, default `redis://localhost:6379`

Ensure `cookies.txt` and `data/images/` exist and are writable.

## Usage
In production the bot and its Celery worker run as systemd services and deploy automatically
when `Main` passes CI. See [deploy/README.md](deploy/README.md).

To run locally, start the worker and the bot in two terminals:
```bash
celery -A audio.tasks worker --concurrency=1
python app.py
```
The bot will start, load its cogs, connect to the configured service, and begin processing events.

## Testing
```bash
pip install -r requirements-dev.txt
docker compose -f docker-compose.test.yml up -d --wait   # throwaway Postgres on port 5433
pytest
ruff check .
```
Without the test database running, database tests are skipped and the rest still run. Tests
refuse to touch any database whose name doesn't contain `test`. CI runs everything on every push
and pull request.

## Project structure
```
CraigBot/
├── audio/
├── cogs/                  # Modular extensions
├── data/
│   └── images/            # Image assets
├── database/              # Persistent data
├── deploy/                # systemd units and deploy script
├── tests/                 # pytest suite
├── utils/                 # Helper functions
├── app.py                 # Main entry point
├── craig.py               # Core bot logic
├── cookies.txt            # Session cookies
├── quotes.py              # Quotes module
├── requirements.txt       # Dependencies
├── requirements-dev.txt   # Test and lint dependencies
├── example.env            # Example config
└── .gitignore
```

## License
This project is licensed under the MIT License, see the LICENSE file for details.

---
Made from pain and frustration.
