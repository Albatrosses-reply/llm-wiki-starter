"""위키 페이지: 목록, 원고·개념 요약표, source 페이지 쓰기, 개념 페이지, index.md."""
from __future__ import annotations

import re
from pathlib import Path

from . import config
from .util import TODAY, fm_dump, fm_parse, fm_read, fm_write, quote_found, read_text, sections, slug, write_text

LLM_DRAFT = "<!-- llm-draft"
HUMAN_HEADS = {"contribution": "## ✍️ Contribution (사람)", "caveats": "## ⚠️ Caveats (사람)", "relation": "## 🧭 내 연구와의 관계 (사람)"}
PDF_REF = re.compile(r"\(PDF p\.\s*(\d+)(?:\s*[-~–]\s*(\d+))?\)")


def all_pages(kind: str = "source") -> list[dict]:
    d = {"source": config.SOURCES, "concept": config.CONCEPTS, "project": config.PROJECTS}[kind]
    out = []
    for p in sorted(d.glob("*.md")) if d.exists() else []:
        if p.name.startswith("_"):
            continue
        meta, body = fm_read(p)
        out.append({"path": p, "name": p.stem, "meta": meta, "body": body})
    return out


def known_zotero_keys() -> dict[str, str]:
    return {str(p["meta"].get("zotero_key")): p["name"] for p in all_pages() if p["meta"].get("zotero_key")}


def project_digest() -> tuple[str, set[str]]:
    rows, slugs = [], set()
    for p in all_pages("project"):
        slugs.add(p["name"])
        rows.append(f"- {p['name']}: {p['meta'].get('title', '')} :: {p['meta'].get('summary', '')}")
    return ("\n".join(rows) or "(없음)"), slugs


def concept_digest() -> str:
    return "\n".join(f"- {p['name']}: {p['meta'].get('title', '')}" for p in all_pages("concept")) or "(없음)"


def human_state(block: str | None) -> str:
    if block is None:
        return "missing"
    if LLM_DRAFT in block:
        return "draft"
    return "human" if re.sub(r"<!--.*?-->", "", block, flags=re.S).strip() else "empty"


# ── 정리·검증 ──
def tidy(s: object, valid_pages: set[int]) -> str:
    """em dash를 쉼표로, 받은 자료에 없는 PDF 쪽 번호는 '(PDF 쪽 확인 필요)'로."""
    s = re.sub(r"\s*—\s*", ", ", str(s or "")).strip()

    def fix(m):
        lo, hi = int(m.group(1)), int(m.group(2) or m.group(1))
        return m.group(0) if valid_pages and all(p in valid_pages for p in range(lo, hi + 1)) else "(PDF 쪽 확인 필요)"
    return PDF_REF.sub(fix, s)


def bullets(items, valid: set[int]) -> str:
    items = [tidy(x, valid) for x in (items or []) if str(x).strip()]
    return "\n".join(f"- {x}" for x in items) or "- 자료에 없음"


def relation_lines(rels: list[dict], topics: list[str], project_slugs: set[str], valid: set[int]) -> list[str]:
    out = []
    for r in rels[:2]:
        t, why = str(r.get("target", "")).strip(), tidy(r.get("why", ""), valid)
        m = re.fullmatch(r"topic-(\d)", t)
        if t in project_slugs:
            out.append(f"- 내 원고 [[{t}]]: {why}")
        elif m and 1 <= int(m.group(1)) <= len(topics):
            out.append(f"- 내 연구 주제 {m.group(1)}({topics[int(m.group(1)) - 1]}): {why}")
    return out or ["- 연결되는 연구 없음(내 원고·연구 주제와 직접 겹치지 않음)."]


def render_source(b: dict, d: dict, cfg: dict, read_pages: list[int], page_texts: list[str], project_slugs: set[str],
                  concept_slugs: list[str]) -> tuple[str, list[str]]:
    """(페이지 텍스트, 메모). 서지는 Zotero 값(b)만 쓰고, 모델 답(d)은 정리·검증해서 넣는다."""
    notes = []
    valid = set(read_pages)
    topics = [t for t in cfg["me"].get("topics") or [] if str(t).strip()]
    quotes = []
    for q in d.get("quotes") or []:
        txt, pg = str(q.get("text", "")).strip().strip('"“”'), int(q.get("page") or 0)
        if pg in valid and len(txt.split()) <= 15 and 1 <= pg <= len(page_texts) and len(quotes) < 2:
            if quote_found(txt, page_texts[pg - 1]):
                quotes.append(f'> "{txt}" (PDF p. {pg}) [↗](zotero://open-pdf/library/items/{b["pdf_key"]}?page={pg})')
                continue
        notes.append("PDF에서 확인 안 된 인용문 지움")
    read = re.sub(r"-{2,}|[<>]", " ", str(d.get("read") or ("초록" if not read_pages else ""))).strip()[:60]
    mark = f"<!-- llm-draft: 자동 초안 {TODAY} · 근거 {read}. 고쳐 쓰면 이 줄을 지운다 -->"
    links = [f"[DOI](https://doi.org/{b['doi']})" if b["doi"] else "", f"[Zotero](zotero://select/library/items/{b['zotero_key']})",
             f"[PDF](zotero://open-pdf/library/items/{b['pdf_key']})" if b["pdf_key"] else ""]
    projects = sorted({ln.split("[[")[1].split("]]")[0] for ln in relation_lines(d.get("relations") or [], topics, project_slugs, valid) if "[[" in ln})
    meta = {"type": "source", "citekey": b["citekey"], "title": b["title"], "authors": b["authors"], "year": b["year"],
            "venue": b["venue"], "doi": b["doi"], "zotero_key": b["zotero_key"], "pdf_key": b["pdf_key"],
            "status": "skimmed", "confidence": "medium" if read_pages else "low", "human_sections_done": False,
            "summary": tidy(d.get("summary"), valid)[:200], "concepts": concept_slugs, "projects": projects,
            "tags": [slug(t, 4) for t in (d.get("tags") or [])][:6],
            "read_scope": (f"PDF p.{', '.join(map(str, read_pages))}" if read_pages else "초록만(PDF 없음)"),
            "created": TODAY, "updated": TODAY}
    body = "\n".join([
        f"# {b['title']}",
        f"{'; '.join(b['authors'])} · *{b['venue']}* · {b['year'] or ''} · " + " · ".join(x for x in links if x), "",
        "> [!abstract] 초록 (Zotero)", "> " + (b["abstract"] or "(Zotero에 초록 없음)"), "",
        HUMAN_HEADS["contribution"], "<!-- human -->", mark, tidy(d.get("contribution"), valid) or "자료에 없음", "",
        HUMAN_HEADS["caveats"], "<!-- human -->", mark, bullets(d.get("caveats"), valid), "",
        HUMAN_HEADS["relation"], "<!-- human -->", mark, *relation_lines(d.get("relations") or [], topics, project_slugs, valid), "",
        "## 🔬 Research Question", bullets(d.get("rq"), valid), "",
        "## 🛠️ 연구 방법론", "### 연구 설계", tidy(d.get("design"), valid) or "자료에 없음", "",
        "### 데이터", tidy(d.get("data"), valid) or "자료에 없음", "",
        "### 식별 전략 · 분석 방법", tidy(d.get("method"), valid) or "자료에 없음", "",
        "## 📊 주요 결과", bullets(d.get("findings"), valid), "", "### 메커니즘", tidy(d.get("mechanism"), valid) or "자료에 없음", "",
        "## ⚠️ 저자가 밝힌 한계", bullets(d.get("limitations"), valid), "",
        "## 🔮 저자 제안 미래 연구", bullets(d.get("future"), valid), "",
        "## 🧩 개념", "\n".join(f"- [[{c}]]" for c in concept_slugs) or "- 없음", "",
        "## 📌 인용문", "\n".join(quotes) or ("(확인된 인용문 없음)" if read_pages else "(PDF 없음, 초록만으로 작성)"), "",
    ])
    if not read_pages:
        notes.append("PDF 없음: 초록만으로 작성")
    return fm_dump(meta, body).rstrip() + "\n", notes


def keep_human_sections(old_text: str, new_text: str) -> str:
    """다시 만들 때 사람이 쓴 섹션(표식 없음)은 옛 내용을 그대로 둔다."""
    old = dict(sections(fm_parse(old_text)[1]))
    meta, body = fm_parse(new_text)
    for key, head in HUMAN_HEADS.items():
        blk = old.get(head)
        if blk is not None and human_state(blk) == "human":
            lines, out, i = body.split("\n"), [], 0
            while i < len(lines):
                if lines[i].strip() == head:
                    out += [lines[i], blk.strip("\n"), ""]
                    i += 1
                    while i < len(lines) and not lines[i].startswith("## "):
                        i += 1
                    continue
                out.append(lines[i])
                i += 1
            body = "\n".join(out)
    return fm_dump(meta, body).rstrip() + "\n"


# ── 개념 ──
def upsert_concepts(concepts: list[dict], citekey: str) -> list[str]:
    """없는 개념은 stub 페이지로 만들고, 있으면 '문헌에서의 쓰임'에 이 논문 한 줄을 덧붙인다. slug 목록을 돌려준다."""
    out = []
    for c in (concepts or [])[:3]:
        s = slug(c.get("slug") or c.get("name") or "", 5)
        if not s or s == "untitled":
            continue
        path = config.CONCEPTS / f"{s}.md"
        line = f"- [[{citekey}]]"
        if path.exists():
            text = read_text(path)
            if line not in text:
                write_text(path, text.rstrip() + "\n" + line + "\n")
        else:
            meta = {"type": "concept", "title": str(c.get("name") or s), "kind": c.get("kind") or "phenomenon",
                    "status": "stub", "created": TODAY, "updated": TODAY}
            body = f"# {meta['title']}\n\n## 정의 (자동 초안)\n{re.sub(chr(8212), ',', str(c.get('definition') or ''))}\n\n## 문헌에서의 쓰임\n{line}\n"
            fm_write(path, meta, body)
        out.append(s)
    return list(dict.fromkeys(out))


# ── index ──
def build_index() -> int:
    src = all_pages()
    lines = ["# 위키 색인", "", f"source {len(src)} · concept {len(all_pages('concept'))} · project {len(all_pages('project'))} · {TODAY} 갱신", "",
             "## 논문", ""]
    for p in sorted(src, key=lambda x: (-(x["meta"].get("year") or 0), x["name"])):
        m = p["meta"]
        lines.append(f"- [[{p['name']}]] ({m.get('year', '')}) {m.get('summary', '')}")
    lines += ["", "## 개념", ""] + [f"- [[{p['name']}]] {p['meta'].get('title', '')} ({p['meta'].get('status', '')})" for p in all_pages("concept")]
    lines += ["", "## 내 원고", ""] + [f"- [[{p['name']}]] {p['meta'].get('title', '')}" for p in all_pages("project")]
    write_text(config.INDEX, "\n".join(lines) + "\n")
    return len(src)


def log(entry: str, items: list[str]) -> None:
    text = read_text(config.LOG) if config.LOG.exists() else "# 작업 기록\n"
    write_text(config.LOG, text.rstrip() + f"\n\n## [{TODAY}] {entry}\n" + "".join(f"- {x}\n" for x in items))


def page_path(citekey: str) -> Path:
    return config.SOURCES / f"{citekey}.md"
