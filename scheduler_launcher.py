"""Run the existing daily CLI without a console; retain diagnostics locally."""
import datetime as dt
from pathlib import Path
import runpy
import sys
import traceback

root = Path(__file__).resolve().parent
(root / 'local').mkdir(exist_ok=True)
with (root / 'local' / 'scheduler.log').open('a', encoding='utf-8', buffering=1) as log:
    sys.stdout = sys.stderr = log
    print(f'\nLauncher {dt.datetime.now(dt.timezone.utc).isoformat()}', flush=True)
    try:
        runpy.run_path(str(root / 'daily.py'), run_name='__main__')
    except Exception:
        traceback.print_exc()
        sys.exit(1)
