"""매일 실행(`wiki daily`): 수집 → ingest → 브리핑 → 색인 → git 커밋. 한 단계가 실패해도 다음 단계는 돈다."""
from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
import time
import traceback

from . import briefing, collect, config, ingest, pages
from .util import TODAY, now, write_text

LOCK = config.STATE / "daily.lock"
LOGF = config.STATE / "daily.log"


def _step(name: str, fn, out: list[str]) -> None:
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            fn()
        out.append(f"[{now()}] {name}: {buf.getvalue().strip() or 'ok'}")
    except Exception:  # noqa: BLE001
        out.append(f"[{now()}] {name} 실패\n{buf.getvalue()}{traceback.format_exc(limit=3)}")


def git_commit(cfg: dict) -> str:
    if not (config.VAULT / ".git").exists() or not shutil.which("git"):
        return "git 없음(건너뜀)"
    name, email = cfg["me"].get("name") or "wikikit", cfg["me"].get("email") or "wikikit@localhost"
    g = ["git", "-C", str(config.VAULT), "-c", f"user.name={name}", "-c", f"user.email={email}"]
    subprocess.run(g + ["add", "-A"], capture_output=True)
    r = subprocess.run(g + ["commit", "-q", "-m", f"daily: {TODAY}"], capture_output=True, text=True)
    return "커밋함" if r.returncode == 0 else "변경 없음"


def run(cfg: dict) -> int:
    config.ensure_dirs()
    if LOCK.exists() and time.time() - LOCK.stat().st_mtime < 3 * 3600:
        print("이미 실행 중(.wiki/daily.lock). 건너뜀")
        return 0
    write_text(LOCK, str(os.getpid()))
    out = [f"[{now()}] daily 시작"]
    try:
        if not cfg["daily"].get("enabled", True):
            out.append("wiki.toml [daily] enabled = false, 건너뜀")
            return 0
        _step("수집", lambda: collect.run(cfg), out)
        _step("ingest", lambda: ingest.run(cfg), out)
        _step("브리핑", lambda: briefing.run(cfg), out)
        _step("색인", lambda: print(f"index {pages.build_index()}편"), out)
        out.append(f"[{now()}] git: {git_commit(cfg)}")
        return 0
    finally:
        out.append(f"[{now()}] daily 끝")
        old = LOGF.read_text(encoding="utf-8")[-200_000:] if LOGF.exists() else ""
        write_text(LOGF, old + "\n".join(out) + "\n")
        print("\n".join(out))
        LOCK.unlink(missing_ok=True)
