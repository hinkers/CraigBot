import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(
    sys.platform == 'win32', reason='deploy.sh runs on the Linux server; exercised in CI'
)


def write_stub(directory, name, body):
    path = directory / name
    path.write_text('#!/usr/bin/env bash\n' + body)
    path.chmod(0o755)


def run_deploy(tmp_path, *, git_exit=0, pids=('100', '100'), active=True):
    """Run deploy.sh in a fake checkout with git/sudo/systemctl/sleep/journalctl stubbed on PATH."""
    app = tmp_path / 'app'
    (app / 'deploy').mkdir(parents=True)
    shutil.copy(REPO / 'deploy' / 'deploy.sh', app / 'deploy' / 'deploy.sh')
    (app / 'requirements.txt').write_text('')
    venv_bin = app / 'venv' / 'bin'
    venv_bin.mkdir(parents=True)
    write_stub(venv_bin, 'pip', 'echo "pip $*" >> "$CALLS"\n')

    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    write_stub(bin_dir, 'git', f'echo "git $*" >> "$CALLS"\nexit {git_exit}\n')
    write_stub(bin_dir, 'sudo', 'echo "sudo $*" >> "$CALLS"\n')
    write_stub(bin_dir, 'sleep', 'true\n')
    write_stub(bin_dir, 'journalctl', 'echo "journal for $*"\n')
    # The first MainPID read per unit (2 total) returns pids[0]; later reads return pids[1]
    write_stub(bin_dir, 'systemctl', f'''
case "$1" in
  show)
    n=$(( $(cat "$PID_READS" 2>/dev/null || echo 0) + 1 ))
    echo "$n" > "$PID_READS"
    if [ "$n" -le 2 ]; then echo {pids[0]}; else echo {pids[1]}; fi ;;
  is-active) exit {0 if active else 3} ;;
esac
''')

    calls = tmp_path / 'calls.log'
    env = {
        **os.environ,
        'PATH': f'{bin_dir}{os.pathsep}{os.environ["PATH"]}',
        'CALLS': str(calls),
        'PID_READS': str(tmp_path / 'pid_reads'),
    }
    result = subprocess.run(
        ['bash', str(app / 'deploy' / 'deploy.sh')],
        env=env, capture_output=True, text=True, cwd=tmp_path,
    )
    recorded = calls.read_text().splitlines() if calls.exists() else []
    return result, recorded


def test_healthy_deploy_pulls_installs_and_restarts(tmp_path):
    result, calls = run_deploy(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert calls == [
        'git pull --ff-only',
        'pip install --quiet --disable-pip-version-check -r requirements.txt',
        'sudo systemctl restart craigbot-celery craigbot',
    ]


def test_failed_pull_stops_before_restarting(tmp_path):
    result, calls = run_deploy(tmp_path, git_exit=1)

    assert result.returncode != 0
    assert not any(call.startswith('sudo') for call in calls)


def test_crash_looping_service_fails_deploy(tmp_path):
    result, _ = run_deploy(tmp_path, pids=('100', '200'))

    assert result.returncode == 1
    assert 'UNHEALTHY' in result.stdout
    assert 'journal for' in result.stdout


def test_inactive_service_fails_deploy(tmp_path):
    result, _ = run_deploy(tmp_path, active=False)

    assert result.returncode == 1


def test_service_without_main_process_fails_deploy(tmp_path):
    result, _ = run_deploy(tmp_path, pids=('0', '0'))

    assert result.returncode == 1
