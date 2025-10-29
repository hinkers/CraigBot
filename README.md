# CraigBot
A Python-based bot to automate various tasks, he's lightweight, modular, and easy to configure.

## Table of Contents
- [What is it](#what-is-it)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Project structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)

## What is it
CraigBot is a lightweight bot written in Python intended to automate repetitive or interactive tasks.  
It supports modular extensions and simple configuration through environment variables.

## Features
- Easily configured via `.env` (see `example.env`)
- Modular design using Python cogs for additional functionality
- Quote feature (via `quotes.py`)
- Cookie/session support (`cookies.txt`)
- Shell script to launch (`run.sh`)
- Dependency management via `requirements.txt`

## Prerequisites
Before you use this bot make sure you have:
- Python 3.8+
- pip
- Basic command-line familiarity
- API tokens or credentials for any connected services

## Installation
```bash
git clone https://github.com/hinkers/CraigBot.git
cd CraigBot
cp example.env .env
# Edit .env with your configuration
pip install -r requirements.txt
```

## Configuration
Edit `.env` and configure your environment variables:

```
BOT_TOKEN=your_bot_token_here
DB_PATH=./database/your.db
COOKIE_FILE=./cookies.txt
```

Ensure `cookies.txt`, `database/`, and `data/images/` exist and are writable.

## Usage
To launch the bot:
```bash
./run.sh
```
Or manually:
```bash
python app.py
```
The bot will start, load its cogs, connect to the configured service, and begin processing events.

## Project structure
```
CraigBot/
├── audio/
├── cogs/                  # Modular extensions
├── data/
│   └── images/            # Image assets
├── database/              # Persistent data
├── utils/                 # Helper functions
├── app.py                 # Main entry point
├── craig.py               # Core bot logic
├── cookies.txt            # Session cookies
├── quotes.py              # Quotes module
├── requirements.txt       # Dependencies
├── run.sh                 # Launch script
├── example.env            # Example config
└── .gitignore
```

## License
This project is licensed under the MIT License — see the LICENSE file for details.

---
Made from pain and frustration.
