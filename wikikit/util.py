"""공용 도구: 텍스트 정규화, frontmatter 읽기·쓰기, 파일 읽기 재시도, 인용문 대조, JSON 상태 파일."""
from __future__ import annotations

import errno
import html
import json
import re
import time
import unicodedata
from datetime import date, datetime
from pathlib import Path

import yaml

TODAY = date.today().isoformat()
WS = re.compile(r"\s+")


# ── 텍스트 ──
def clean(s) -> str:
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", str(s))
    return WS.sub(" ", html.unescape(s)).strip()


def norm_doi(doi) -> str:
    d = (doi or "").strip()
    d = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", d, flags=re.I)
    d = re.sub(r"^doi:\s*", "", d, flags=re.I)
    return d.strip().rstrip(".").lower()


def fold(s: str) -> str:
    d = unicodedata.normalize("NFKD", s or "")
    return unicodedata.normalize("NFC", "".join(c for c in d if unicodedata.category(c) != "Mn")).lower()


def norm_title(s: str) -> str:
    return re.sub(r"[\W_]", "", fold(clean(s)))


def ascii_fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()


def slug(s: str, max_words: int = 5, fallback: str = "untitled") -> str:
    words = re.findall(r"[a-z0-9]+", ascii_fold(s).lower())
    stop = {"a", "an", "the", "of", "and", "or", "in", "on", "for", "to", "with", "from", "by", "at", "as"}
    kept = [w for w in words if w not in stop] or words
    return "-".join(kept[:max_words]) or fallback


def surname(name: str) -> str:
    name = (name or "").strip()
    if "," in name:
        return name.split(",")[0].strip()
    parts = name.split()
    return parts[-1] if parts else ""


# ── 파일 ──
def read_text(path: Path, tries: int = 4) -> str:
    """클라우드 동기화 폴더는 다른 프로세스가 쓰는 중인 파일을 읽을 때 잠금 오류를 낸다. 잠깐 쉬고 다시 읽는다."""
    for i in range(tries):
        try:
            return Path(path).read_text(encoding="utf-8")
        except OSError as e:
            if e.errno not in (errno.EDEADLK, errno.EACCES, 13, 32) or i == tries - 1:
                raise
            time.sleep(2 ** i)
    raise OSError("unreachable")


def write_text(path: Path, s: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(s, encoding="utf-8", newline="\n")


def jload(path: Path, default):
    try:
        return json.loads(read_text(path))
    except (OSError, json.JSONDecodeError):
        return default


def jsave(path: Path, obj) -> None:
    write_text(path, json.dumps(obj, ensure_ascii=False, indent=1))


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ── frontmatter ──
FM_RE = re.compile(r"\A---\n(.*?)\n---[ \t]*\n?", re.S)


def fm_parse(text: str) -> tuple[dict, str]:
    text = text.replace("\r\n", "\n")
    m = FM_RE.match(text)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    return (meta if isinstance(meta, dict) else {}), text[m.end():]


class _Dumper(yaml.SafeDumper):
    pass


_Dumper.add_representer(str, lambda d, s: d.represent_scalar("tag:yaml.org,2002:str", s, style="|" if "\n" in s else None))


def fm_dump(meta: dict, body: str) -> str:
    y = yaml.dump(meta, Dumper=_Dumper, allow_unicode=True, sort_keys=False, default_flow_style=None, width=4096)
    return f"---\n{y}---\n" + (body if body.startswith("\n") else "\n" + body)


def fm_read(path: Path) -> tuple[dict, str]:
    return fm_parse(read_text(path))


def fm_write(path: Path, meta: dict, body: str) -> None:
    write_text(path, fm_dump(meta, body).rstrip() + "\n")


def sections(body: str) -> list[tuple[str, str]]:
    parts, cur, buf = [], "", []
    for ln in body.splitlines():
        if ln.startswith("## "):
            parts.append((cur, "\n".join(buf)))
            cur, buf = ln.strip(), []
        else:
            buf.append(ln)
    parts.append((cur, "\n".join(buf)))
    return parts


# ── 인용문 대조 ──
def _norm_q(s: str) -> list[str]:
    s = (s or "").replace("­", "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("ﬁ", "fi").replace("ﬂ", "fl").replace("ﬀ", "ff").replace("ﬃ", "ffi")
    a, b = re.sub(r"-\s*\n\s*", "-", s), re.sub(r"-\s*\n\s*", "", s)
    return [WS.sub(" ", x).strip().lower() for x in (a, b)]


def quote_found(quote: str, page_text: str) -> bool:
    """인용문이 그 쪽 텍스트에 실제로 있는지(줄바꿈 하이픈·따옴표 차이 무시)."""
    q = _norm_q(quote)[0].strip(' ."')
    return bool(q) and any(q in t for t in _norm_q(page_text))
