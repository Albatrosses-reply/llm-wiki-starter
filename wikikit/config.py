"""경로와 설정. 볼트(이 저장소 폴더)가 기준이고, 학생별 설정은 wiki.toml 한 파일에 둔다."""
from __future__ import annotations

import os
import tomllib
from copy import deepcopy
from pathlib import Path

PKG = Path(__file__).resolve().parent
VAULT = Path(os.environ.get("WIKI_HOME") or PKG.parent).resolve()
WIKI = VAULT / "notes"       # 위키 페이지 (wiki 명령과 이름이 겹치지 않게)
SOURCES = WIKI / "sources"
CONCEPTS = WIKI / "concepts"
PROJECTS = WIKI / "projects"
REPORTS = VAULT / "reports"
BRIEFINGS = REPORTS / "briefing"
BRIEFING = VAULT / "BRIEFING.md"
INDEX = VAULT / "index.md"
LOG = VAULT / "log.md"
STATE = VAULT / ".wiki"          # 캐시·상태·로그 (git에 넣지 않음)
CFG_FILE = VAULT / "wiki.toml"

DEFAULTS: dict = {
    "me": {"name": "", "email": "", "topics": []},
    "zotero": {"data_dir": "", "inbox_collection": "Wiki Inbox", "inbox_tag": "wiki-inbox", "port": 23119},
    "codex": {"model": "", "reasoning_effort": "medium", "timeout_s": 600},
    "daily": {"enabled": True, "time": "08:00", "ingest_max": 3, "candidates_max": 10, "lookback_days": 14},
    "journals": {"fields": [], "extra": [], "keywords": []},
    "library": {"name": "", "proxy_suffix": "", "ebsco_search": ""},
}


def _merge(base: dict, over: dict) -> dict:
    out = deepcopy(base)
    for k, v in (over or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load() -> dict:
    """wiki.toml을 읽어 기본값과 합친다. 파일이 없으면 기본값."""
    try:
        with open(CFG_FILE, "rb") as f:
            user = tomllib.load(f)
    except FileNotFoundError:
        user = {}
    return _merge(DEFAULTS, user)


def zotero_dir(cfg: dict) -> Path:
    d = (cfg.get("zotero") or {}).get("data_dir") or ""
    return Path(d).expanduser() if d else Path.home() / "Zotero"


def zotero_api(cfg: dict) -> str:
    return f"http://127.0.0.1:{cfg['zotero']['port']}/api/users/0"


def zotero_connector(cfg: dict) -> str:
    return f"http://127.0.0.1:{cfg['zotero']['port']}/connector"


def ensure_dirs() -> None:
    for d in (SOURCES, CONCEPTS, PROJECTS, BRIEFINGS, STATE, STATE / "runs"):
        d.mkdir(parents=True, exist_ok=True)
