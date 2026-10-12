"""Zotero 접근. 읽기는 로컬 API(Zotero 7, 설정 › 고급 › '다른 앱과 통신 허용'), 쓰기는 커넥터의 새 항목 저장뿐.
Zotero 데이터베이스 파일은 절대 직접 고치지 않는다."""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from . import config
from .util import clean, norm_doi, slug, surname

HDR = {"Zotero-API-Version": "3"}
CONNECTOR_HDR = {"X-Zotero-Connector-API-Version": "3", "Content-Type": "application/json"}


class ZoteroError(RuntimeError):
    pass


def _get(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers=HDR)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def ping(cfg: dict) -> bool:
    try:
        with urllib.request.urlopen(f"{config.zotero_connector(cfg)}/ping", timeout=4) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def api_ok(cfg: dict) -> bool:
    try:
        _get(f"{config.zotero_api(cfg)}/collections?limit=1", timeout=5)
        return True
    except Exception:  # noqa: BLE001
        return False


def launch(cfg: dict, wait: int = 60) -> bool:
    """Zotero가 꺼져 있으면 띄운다(창은 뒤로). 켜지면 True."""
    if ping(cfg):
        return True
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run(["open", "-g", "-a", "Zotero"], check=False, capture_output=True)
        elif system == "Windows":
            for exe in (Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Zotero" / "zotero.exe",
                        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Zotero" / "zotero.exe",
                        Path(os.environ.get("LOCALAPPDATA", "")) / "Zotero" / "zotero.exe"):
                if exe.exists():
                    subprocess.Popen([str(exe)], close_fds=True)
                    break
        else:
            z = shutil.which("zotero")
            if z:
                subprocess.Popen([z], close_fds=True)
    except OSError:
        return False
    for _ in range(wait):
        if ping(cfg):
            time.sleep(5)   # Better BibTeX 준비
            return True
        time.sleep(1)
    return False


def _pages(url: str) -> list[dict]:
    out, start = [], 0
    while True:
        sep = "&" if "?" in url else "?"
        batch = _get(f"{url}{sep}format=json&limit=100&start={start}")
        out.extend(batch)
        if len(batch) < 100:
            return out
        start += 100


def find_collection(cfg: dict, name: str) -> str | None:
    for c in _pages(f"{config.zotero_api(cfg)}/collections"):
        if (c.get("data") or {}).get("name") == name:
            return c["key"]
    return None


def inbox_items(cfg: dict) -> list[dict]:
    """'Wiki Inbox' 컬렉션의 항목 + 'wiki-inbox' 태그가 붙은 항목(`wiki add`로 넣은 것). 첨부·노트 제외."""
    api = config.zotero_api(cfg)
    found: dict[str, dict] = {}
    ckey = find_collection(cfg, cfg["zotero"]["inbox_collection"])
    if ckey:
        for it in _pages(f"{api}/collections/{ckey}/items/top"):
            found[it["key"]] = it
    tag = cfg["zotero"]["inbox_tag"]
    if tag:
        for it in _pages(f"{api}/items/top?tag={urllib.parse.quote(tag)}"):
            found[it["key"]] = it
    return [it for it in found.values() if (it.get("data") or {}).get("itemType") not in ("attachment", "note", "annotation")]


def children(cfg: dict, key: str) -> list[dict]:
    return _get(f"{config.zotero_api(cfg)}/items/{key}/children?format=json")


def pdf_of(cfg: dict, key: str) -> tuple[str, Path] | None:
    """(첨부 키, 파일 경로). 저장 파일과 링크 파일 둘 다."""
    for ch in children(cfg, key):
        d = ch.get("data") or {}
        if d.get("itemType") != "attachment" or d.get("contentType") != "application/pdf":
            continue
        mode, p = d.get("linkMode"), None
        if mode in ("imported_file", "imported_url") and d.get("filename"):
            p = config.zotero_dir(cfg) / "storage" / ch["key"] / d["filename"]
        elif mode == "linked_file" and d.get("path"):
            raw = d["path"]
            p = Path(raw[len("attachments:"):]) if raw.startswith("attachments:") else Path(raw)
        if p and p.exists():
            return ch["key"], p
    return None


def doi_of(d: dict) -> str:
    doi = d.get("DOI") or ""
    if not doi:
        for line in (d.get("extra") or "").splitlines():
            if line.lower().startswith("doi:"):
                doi = line.split(":", 1)[1]
    return norm_doi(doi)


def authors_of(d: dict) -> list[str]:
    out = []
    for c in d.get("creators") or []:
        if c.get("creatorType", "author") != "author":
            continue
        out.append(c["name"] if c.get("name") else f"{c.get('lastName', '')}, {c.get('firstName', '')}".strip(", "))
    return out


def year_of(d: dict) -> int | None:
    m = re.search(r"(1[5-9]\d\d|20\d\d)", d.get("date") or "")
    return int(m.group(1)) if m else None


def venue_of(d: dict) -> str:
    for f in ("publicationTitle", "proceedingsTitle", "bookTitle", "repository", "university", "institution", "publisher"):
        if d.get(f):
            return clean(d[f])
    return ""


def make_citekey(d: dict, taken: set[str]) -> str:
    """Better BibTeX 키가 없을 때: 첫 저자 성 + EtAl + 연도 (+ a, b …)."""
    auths = authors_of(d)
    base = slug(surname(auths[0]) if auths else (d.get("title") or "untitled"), 1).capitalize() or "Untitled"
    base = re.sub(r"[^A-Za-z0-9]", "", base) or "Untitled"
    key = f"{base}{'EtAl' if len(auths) > 2 else ''}{year_of(d) or ''}"
    out, i = key, 0
    while out.lower() in taken:
        out = key + "abcdefghijklmnopqrstuvwxyz"[i]
        i += 1
    return out


def bib(cfg: dict, it: dict, taken: set[str]) -> dict:
    """위키 페이지에 쓸 서지. 서지 필드는 항상 이 값만 쓴다(모델이 쓴 값은 버린다)."""
    d = it.get("data") or it
    ck = d.get("citationKey") or make_citekey(d, taken)
    pdf = pdf_of(cfg, it["key"])
    return {"citekey": ck, "zotero_key": it["key"], "title": clean(d.get("title")), "authors": authors_of(d),
            "year": year_of(d), "venue": venue_of(d), "doi": doi_of(d), "abstract": clean(d.get("abstractNote")),
            "pdf_key": pdf[0] if pdf else "", "pdf_path": str(pdf[1]) if pdf else ""}


# ── 쓰기: 새 항목 추가(커넥터) ──
def crossref_to_item(msg: dict, tag: str) -> dict:
    doi = norm_doi(msg.get("DOI"))
    item = {"itemType": "journalArticle", "title": clean((msg.get("title") or [""])[0]),
            "publicationTitle": clean((msg.get("container-title") or [""])[0]), "DOI": doi,
            "url": f"https://doi.org/{doi}", "abstractNote": clean(re.sub(r"^\s*abstract\s*", "", clean(msg.get("abstract")), flags=re.I)),
            "volume": msg.get("volume", ""), "issue": msg.get("issue", ""), "pages": msg.get("page", ""),
            "creators": [{"firstName": a.get("given", ""), "lastName": a["family"], "creatorType": "author"}
                         for a in msg.get("author") or [] if a.get("family")],
            "tags": [{"tag": tag}], "libraryCatalog": "Crossref"}
    for k in ("published-print", "published-online", "issued"):
        parts = ((msg.get(k) or {}).get("date-parts") or [[None]])[0]
        if parts and parts[0]:
            item["date"] = "-".join(f"{int(p):02d}" if i else str(p) for i, p in enumerate(parts) if p)
            break
    return {k: v for k, v in item.items() if v not in ("", None)}


def save_items(cfg: dict, items: list[dict]) -> tuple[bool, str]:
    """커넥터로 새 항목 저장. Zotero 창에서 지금 선택한 라이브러리에 들어간다."""
    body = json.dumps({"sessionID": uuid.uuid4().hex, "uri": "http://127.0.0.1/", "items": items}).encode("utf-8")
    req = urllib.request.Request(f"{config.zotero_connector(cfg)}/saveItems", data=body, method="POST", headers=CONNECTOR_HDR)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status in (200, 201), ""
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001
        return False, str(e)
