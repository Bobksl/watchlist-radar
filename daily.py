"""Exchange-aware scheduled scan. Run every 15 minutes; collect once per US session."""
import argparse
import contextlib
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
sys.path.append(str(ROOT / "local" / "dependencies"))  # preserve the scanner's installed numpy/pandas


def calendar():
    import exchange_calendars
    return exchange_calendars.get_calendar("XNYS")


def session_dates(day, count=5):
    cal = calendar()
    first = cal.date_to_session(str(day), direction="next")
    return cal.sessions_window(first, count)


def session_bounds(day):
    cal = calendar()
    if not cal.is_session(str(day)):
        return None
    return cal.session_open(str(day)).to_pydatetime(), cal.session_close(str(day)).to_pydatetime()


def due(now, state):
    from radar import NY
    day = now.astimezone(NY).date()
    bounds = session_bounds(day)
    if not bounds:
        return False
    opened, closed = bounds
    # One attempt per day: a source outage must not trigger repeated AI spending.
    return (opened + dt.timedelta(minutes=30) <= now < closed
            and state.get("attempt_session") != str(day))


@contextlib.contextmanager
def scan_lock(path):
    """OS releases the lock after a crash; no stale sentinel blocks tomorrow's scan."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as f:
        f.seek(0)
        f.write(b"0")
        f.flush()
        f.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            f.seek(0)
            if os.name == "nt":
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f, fcntl.LOCK_UN)


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix + ".pending")
    pending.write_text(content, encoding="utf-8")
    pending.replace(path)


def save_state(state):
    atomic_write(ROOT / "local" / "refresh.json", json.dumps(state, indent=2))
    # Public errors are stage + exception class only; never raw exceptions with local data.
    public = {k: v for k, v in state.items() if k != "local_error"}
    atomic_write(ROOT / "docs" / "status.json", json.dumps(public, indent=2))


def refresh(now=None, force=False, publish=True, scan=None):
    import radar
    now = now or dt.datetime.now(dt.timezone.utc)
    state_path = ROOT / "local" / "refresh.json"
    with scan_lock(ROOT / "local" / "scan.lock"):
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        if not force and not due(now, state):
            if publish and state.get("publication") == "failed" and state.get("push_attempts", 0) < 3:
                try:
                    state["push_attempts"] = state.get("push_attempts", 0) + 1
                    radar.publish(state.get("run") if state.get("scan") == "success" else None, include_status=True)
                    state.update(publication="push_success", last_push=now.isoformat(), error=None)
                except Exception as e:
                    state.update(local_error=str(e))
                atomic_write(state_path, json.dumps(state, indent=2))
                return "publication_failed" if state["publication"] == "failed" else "publication_retry"
            return "not_due"
        state.update(attempt_session=str(now.astimezone(radar.NY).date()),
                     last_attempt=now.isoformat(), scan="running", publication="pending", push_attempts=0)
        save_state(state)
        stamp = None
        try:
            wl = (ROOT / "watchlist.txt").read_text(encoding="utf-8").split()
            stamp = (scan or radar.run)([t.upper() for t in wl])
            state.update(scan="success", last_success=dt.datetime.now(dt.timezone.utc).isoformat(),
                         run=stamp, error=None)
        except Exception as e:
            state.update(scan="failed", error=f"scan: {type(e).__name__}", local_error=str(e))
        save_state(state)
        if publish:
            try:
                state["push_attempts"] = 1
                radar.publish(stamp, include_status=True)
                state.update(publication="push_success", last_push=dt.datetime.now(dt.timezone.utc).isoformat())
            except Exception as e:
                state.update(publication="failed", error=f"publication: {type(e).__name__}", local_error=str(e))
            # Remote status is the pre-push pending state; verified push receipt stays local.
            atomic_write(state_path, json.dumps(state, indent=2))
        return state["scan"] if state["publication"] != "failed" else "publication_failed"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="explicit manual retry; may spend on AI")
    ap.add_argument("--no-publish", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="due check only, no scan or writes")
    args = ap.parse_args()
    if args.dry_run:
        p = ROOT / "local" / "refresh.json"
        state = json.loads(p.read_text()) if p.exists() else {}
        print(json.dumps({"due": due(dt.datetime.now(dt.timezone.utc), state), "cadence": "10:00 ET session days"}))
    else:
        try:
            result = refresh(force=args.force, publish=not args.no_publish)
            print(result)
            sys.exit(1 if result in ("failed", "publication_failed") else 0)
        except OSError as e:
            print(f"Locked or unavailable: {type(e).__name__}", file=sys.stderr)
            sys.exit(1)
