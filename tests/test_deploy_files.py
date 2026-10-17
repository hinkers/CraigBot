import re
from pathlib import Path

import pytest

DEPLOY = Path(__file__).resolve().parent.parent / 'deploy'
UNITS = ['craigbot.service', 'craigbot-celery.service']
RESTART_COMMAND = 'systemctl restart craigbot-celery craigbot'


@pytest.mark.parametrize('unit', UNITS)
def test_unit_restarts_even_after_clean_exit(unit):
    # !kill/!restart and app.py's error handler both exit with status 0
    assert 'Restart=always' in (DEPLOY / unit).read_text().splitlines()


@pytest.mark.parametrize('unit', UNITS)
def test_unit_is_templated(unit):
    text = (DEPLOY / unit).read_text()

    assert '__USER__' in text
    assert '__APP_DIR__' in text


def test_sudoers_rule_matches_deploy_restart_command():
    assert f'sudo {RESTART_COMMAND}' in (DEPLOY / 'deploy.sh').read_text()
    assert f'/usr/bin/{RESTART_COMMAND}' in (DEPLOY / 'install-services.sh').read_text()


def test_readme_stop_command_matches_celery_command_line():
    # The old worker's command line is ".../python .../venv/bin/celery -A audio.tasks worker ..."
    pattern = re.search(r"pkill -f '([^']+)'", (DEPLOY / 'README.md').read_text()).group(1)
    exec_start = next(
        line for line in (DEPLOY / 'craigbot-celery.service').read_text().splitlines()
        if line.startswith('ExecStart=')
    )

    assert pattern in exec_start


def test_workflow_deploys_the_tested_commit():
    workflow = (DEPLOY.parent / '.github' / 'workflows' / 'ci.yml').read_text()

    assert '"$DEPLOY_USER@$DEPLOY_HOST" "$GITHUB_SHA"' in workflow
