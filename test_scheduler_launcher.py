from pathlib import Path
import shutil
import subprocess
import sys
import pytest


@pytest.mark.parametrize('body,code,diagnostic', [
    ("import sys; print(sys.argv[-1]); sys.exit(7)", 7, '--dry-run'),
    ("raise RuntimeError('test failure')", 1, 'RuntimeError: test failure')])
def test_launcher_preserves_exit_and_logs_arguments_or_traceback(tmp_path, body, code, diagnostic):
    shutil.copyfile(Path(__file__).with_name('scheduler_launcher.py'), tmp_path / 'scheduler_launcher.py')
    (tmp_path / 'daily.py').write_text(body)
    for _ in range(2):
        run = subprocess.run([sys.executable, '-B', str(tmp_path / 'scheduler_launcher.py'), '--dry-run'],
                             capture_output=True, text=True, timeout=10)
        assert run.returncode == code and not run.stdout and not run.stderr
    log = (tmp_path / 'local/scheduler.log').read_text(encoding='utf-8')
    assert log.count(diagnostic) == 2 and log.count('Launcher ') == 2
