"""매일 자동 실행 등록. Windows는 작업 스케줄러(놓친 실행은 PC를 켤 때 바로), macOS는 launchd(잠들어 있었으면 깰 때)."""
from __future__ import annotations

import os
import platform
import plistlib
import subprocess
import sys
from pathlib import Path

from . import config

TASK = "LLMWikiDaily"
LABEL = "com.wikikit.daily"


def _python(windowless: bool = True) -> str:
    exe = Path(sys.executable)
    if platform.system() == "Windows" and windowless:
        w = exe.with_name("pythonw.exe")   # 아침에 검은 창이 뜨지 않게
        if w.exists():
            return str(w)
    return str(exe)


def _ps(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def on(cfg: dict) -> str:
    hh, mm = (cfg["daily"].get("time") or "08:00").split(":")
    vault = str(config.VAULT)
    if platform.system() == "Windows":
        q = lambda s: s.replace("'", "''")  # noqa: E731
        r = _ps(f"""
$a = New-ScheduledTaskAction -Execute '{q(_python())}' -Argument '-m wikikit daily' -WorkingDirectory '{q(vault)}'
$t = New-ScheduledTaskTrigger -Daily -At '{hh}:{mm}'
$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName '{TASK}' -Action $a -Trigger $t -Settings $s -Description 'LLM Wiki daily: collect, ingest, briefing' -Force | Out-Null
'ok'""")
        return "등록함: 매일 " + f"{hh}:{mm}, 놓치면 PC를 켤 때" if "ok" in r.stdout else f"등록 실패: {r.stderr.strip()[:300]}"
    if platform.system() == "Darwin":
        plist = Path.home() / "Library/LaunchAgents" / f"{LABEL}.plist"
        plist.parent.mkdir(parents=True, exist_ok=True)
        with open(plist, "wb") as f:
            plistlib.dump({"Label": LABEL, "ProgramArguments": [_python(), "-m", "wikikit", "daily"], "WorkingDirectory": vault,
                           "EnvironmentVariables": {"WIKI_HOME": vault, "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONUTF8": "1"},
                           "StartCalendarInterval": {"Hour": int(hh), "Minute": int(mm)},
                           "StandardOutPath": str(config.STATE / "launchd.out.log"), "StandardErrorPath": str(config.STATE / "launchd.err.log")}, f)
        uid = os.getuid()
        subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(plist)], capture_output=True)
        r = subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(plist)], capture_output=True, text=True)
        return f"등록함: 매일 {hh}:{mm} (맥이 잠들어 있었으면 깰 때)" if r.returncode == 0 else f"등록 실패: {r.stderr.strip()[:300]}"
    return "이 운영체제는 자동 등록을 지원하지 않습니다. cron에 `python -m wikikit daily`를 넣으세요"


def off() -> str:
    if platform.system() == "Windows":
        r = _ps(f"Unregister-ScheduledTask -TaskName '{TASK}' -Confirm:$false; 'ok'")
        return "해제함" if "ok" in r.stdout else f"해제 실패: {r.stderr.strip()[:200]}"
    if platform.system() == "Darwin":
        plist = Path.home() / "Library/LaunchAgents" / f"{LABEL}.plist"
        subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(plist)], capture_output=True)
        plist.unlink(missing_ok=True)
        return "해제함"
    return "해당 없음"


def status() -> str:
    if platform.system() == "Windows":
        r = _ps(f"$t = Get-ScheduledTask -TaskName '{TASK}' -ErrorAction SilentlyContinue; if ($t) {{ $i = Get-ScheduledTaskInfo -TaskName '{TASK}'; "
                "\"등록됨 · 다음 실행 $($i.NextRunTime) · 마지막 실행 $($i.LastRunTime) · 결과 $($i.LastTaskResult)\" } else { '등록 안 됨' }")
        return r.stdout.strip() or r.stderr.strip()[:200]
    if platform.system() == "Darwin":
        r = subprocess.run(["launchctl", "print", f"gui/{os.getuid()}/{LABEL}"], capture_output=True, text=True)
        return "등록됨" if r.returncode == 0 else "등록 안 됨"
    return "해당 없음"
