"""Codex CLI 호출. 모델은 읽기 전용 샌드박스에서 돌고, 정해진 JSON 스키마의 답만 낸다. 파일은 파이썬이 쓴다.

- `--ignore-user-config`: 학생의 개인 설정(~/.codex/config.toml)이 자동 실행에 섞이지 않게 한다. 로그인은 그대로 쓴다.
- `--sandbox read-only`: 모델이 명령을 실행하더라도 파일을 바꾸지 못하게 한다.
- 실행 전후로 볼트 파일의 수정 시각을 비교해, 바뀐 것이 있으면 결과를 버린다(이중 확인).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from . import config


class CodexError(RuntimeError):
    pass


def exe() -> str | None:
    return shutil.which("codex")


def logged_in() -> tuple[bool, str]:
    x = exe()
    if not x:
        return False, "codex 명령이 없습니다 (npm i -g @openai/codex)"
    try:
        r = subprocess.run([x, "login", "status"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)
    out = (r.stdout + r.stderr).strip()
    return ("logged in" in out.lower()), out.splitlines()[0] if out else ""


def _snapshot() -> dict[str, float]:
    snap = {}
    for p in config.VAULT.rglob("*"):
        rel = p.relative_to(config.VAULT).parts
        if rel and rel[0] in (".wiki", ".venv", ".git", "__pycache__", ".obsidian"):
            continue
        if p.is_file():
            try:
                snap[str(p)] = p.stat().st_mtime
            except OSError:
                pass
    return snap


def run(prompt: str, schema: Path, cfg: dict, label: str = "codex") -> tuple[dict, dict]:
    """(답 JSON, 정보{seconds, tokens}). 실패하면 CodexError."""
    x = exe()
    if not x:
        raise CodexError("codex 명령이 없습니다")
    c = cfg["codex"]
    with tempfile.TemporaryDirectory(prefix="wikikit-") as td:
        out = Path(td) / "out.json"
        cmd = [x, "exec", "-", "--sandbox", "read-only", "--skip-git-repo-check", "--ephemeral", "--ignore-user-config",
               "--output-schema", str(schema), "-o", str(out), "-C", str(config.VAULT), "--color", "never"]
        if c.get("model"):
            cmd += ["-m", c["model"]]
        if c.get("reasoning_effort"):
            cmd += ["-c", f'model_reasoning_effort="{c["reasoning_effort"]}"']
        before = _snapshot()
        t0 = time.time()
        env = dict(os.environ, PYTHONUTF8="1")
        try:
            r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=int(c.get("timeout_s", 600)), env=env)
        except subprocess.TimeoutExpired as e:
            raise CodexError(f"{label}: 시간 초과({c.get('timeout_s')}초)") from e
        secs = round(time.time() - t0)
        log = (r.stdout or "") + (r.stderr or "")
        (config.STATE / "runs").mkdir(parents=True, exist_ok=True)
        (config.STATE / "runs" / f"{time.strftime('%Y%m%d-%H%M%S')}-{re.sub(r'[^A-Za-z0-9_-]', '_', label)}.log").write_text(
            log[-20000:], encoding="utf-8")
        changed = [p for p, t in _snapshot().items() if before.get(p) != t]
        if changed:
            raise CodexError(f"{label}: 모델 실행 중 볼트 파일이 바뀌어 결과를 버림: {', '.join(Path(p).name for p in changed[:5])}")
        if r.returncode != 0 or not out.exists():
            low = log.lower()
            if "usage limit" in low or "rate limit" in low or "quota" in low:
                raise CodexError(f"{label}: Codex 사용 한도에 걸림. 내일 다시 시도")
            if "login" in low and ("not logged" in low or "unauthorized" in low or "401" in low):
                raise CodexError(f"{label}: Codex 로그인 필요 (codex login)")
            raise CodexError(f"{label}: codex 실패(코드 {r.returncode}) {log.strip().splitlines()[-1][:160] if log.strip() else ''}")
        try:
            data = json.loads(out.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise CodexError(f"{label}: 답이 JSON이 아님") from e
    m = re.search(r"tokens used\s*\n?\s*([\d,]+)", log)
    return data, {"seconds": secs, "tokens": int(m.group(1).replace(",", "")) if m else None}
