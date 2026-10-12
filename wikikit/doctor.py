"""`wiki doctor`: 설치 점검. 문제마다 고치는 방법을 한 줄로 보여 준다. 출력 전체를 조교에게 보내면 대부분 진단된다."""
from __future__ import annotations

import platform
import re
import shutil
import sys

from . import codex, config, schedule, zotero

SYNC_DIRS = re.compile(r"^(OneDrive.*|Google ?Drive.*|GoogleDrive-.*|CloudStorage|iCloud ?Drive.*|Mobile Documents|Dropbox.*|내 드라이브|My Drive)$", re.I)


def in_sync_folder(path: str) -> bool:
    """경로의 폴더 이름 가운데 클라우드 동기화 폴더가 있는지(글자가 섞인 다른 폴더 이름은 무시)."""
    return any(SYNC_DIRS.match(part) for part in re.split(r"[\\/]+", path))


def checks(cfg: dict) -> list[tuple[str, bool, str]]:
    out = []
    v = sys.version_info
    out.append(("파이썬 3.11 이상", v >= (3, 11), f"지금 {v.major}.{v.minor}. setup을 다시 실행"))
    path = str(config.VAULT)
    out.append(("위키 폴더가 동기화 폴더 밖", not in_sync_folder(path),
                f"{path} → OneDrive·Google Drive·iCloud 밖(예: C:\\Users\\<나>\\llm-wiki)으로 폴더를 옮긴 뒤 setup 다시"))
    out.append(("wiki.toml 있음", config.CFG_FILE.exists(), "setup을 다시 실행하거나 wiki.example.toml을 복사"))
    out.append(("연구 주제 적음", bool([t for t in cfg["me"].get("topics") or [] if str(t).strip()]),
                "wiki.toml [me] topics에 연구 주제 1~3줄 (관련도 판단에 씀)"))
    ping = zotero.ping(cfg)
    out.append(("Zotero 실행 중", ping, "Zotero 7을 켠다 (설치: zotero.org)"))
    api = zotero.api_ok(cfg) if ping else False
    out.append(("Zotero 로컬 API 켜짐", api, "Zotero › 설정 › 고급 › '이 컴퓨터의 다른 애플리케이션이 Zotero와 통신하도록 허용' 체크"))
    if api and cfg["zotero"]["inbox_collection"]:
        col = zotero.find_collection(cfg, cfg["zotero"]["inbox_collection"])
        out.append((f"Zotero 컬렉션 '{cfg['zotero']['inbox_collection']}'", bool(col),
                    "Zotero 왼쪽 '내 라이브러리'에서 우클릭 › 새 컬렉션 › 이름 'Wiki Inbox'"))
    out.append(("Zotero 데이터 폴더", (config.zotero_dir(cfg) / "storage").exists() or not ping,
                f"{config.zotero_dir(cfg)} 에 storage가 없음 → Zotero 설정 › 고급 › 파일과 폴더의 데이터 디렉터리를 wiki.toml [zotero] data_dir에"))
    ok, msg = codex.logged_in()
    out.append(("Codex CLI 로그인", ok, f"{msg} → 터미널에서 `codex login` (ChatGPT 계정)"))
    out.append(("git (선택: 변경 기록)", bool(shutil.which("git")), "없어도 동작. 기록을 원하면 git 설치"))
    out.append(("매일 자동 실행", "등록됨" in schedule.status(), "`wiki schedule on`"))
    return out


def run(cfg: dict) -> int:
    print(f"wikikit 점검 · {platform.system()} {platform.release()} · {config.VAULT}")
    bad = 0
    for name, ok, fix in checks(cfg):
        print(f"  {'✓' if ok else '✗'} {name}" + ("" if ok else f"\n      → {fix}"))
        bad += not ok
    print("모두 정상" if not bad else f"고칠 것 {bad}개")
    return 0 if not bad else 1
