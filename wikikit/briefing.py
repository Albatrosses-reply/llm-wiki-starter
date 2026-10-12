"""아침 브리핑: 새 위키 페이지, 관심 저널 신착 후보(관련도 순), PDF가 필요한 논문, 실패. codex exec 한 번.
모델이 실패해도 목록만으로 된 브리핑은 남긴다."""
from __future__ import annotations

import re
import urllib.parse

from . import codex, collect, config, pages
from .util import TODAY, jload, jsave, now, read_text, sections, write_text

PROMPT = config.PKG / "prompts" / "briefing.md"
SCHEMA = config.PKG / "schemas" / "briefing.schema.json"
STATE = config.STATE / "briefing_state.json"


def library_link(cfg: dict, doi: str) -> str:
    lib = cfg["library"]
    if lib.get("ebsco_search") and doi:
        return lib["ebsco_search"].replace("{doi}", urllib.parse.quote(doi, safe=""))
    if lib.get("proxy_suffix") and doi:
        return f"https://doi-org{lib['proxy_suffix']}/{doi}"
    return f"https://doi.org/{doi}" if doi else ""


def relation_line(body: str) -> str:
    blk = dict(sections(body)).get(pages.HUMAN_HEADS["relation"], "")
    lines = [ln[2:] for ln in blk.splitlines() if ln.startswith("- ")]
    return lines[0] if lines else ""


def gather(cfg: dict) -> dict:
    st = jload(STATE, {"briefed_pages": []})
    srcs = pages.all_pages()
    new = [p for p in srcs if p["name"] not in st["briefed_pages"]]
    pdf_needed = [p for p in srcs if "초록만" in str(p["meta"].get("read_scope", ""))]
    ing = jload(config.STATE / "ingest_state.json", {})
    failed = [(k, v) for k, v in ing.items() if not v.get("ok")]
    return {"state": st, "new": new[:15], "cands": collect.fresh(40), "pdf_needed": pdf_needed, "failed": failed,
            "collect": jload(collect.STATE, {})}


def ask_model(cfg: dict, g: dict) -> tuple[dict | None, str]:
    if not g["new"] and not g["cands"]:
        return None, ""
    topics = [t for t in cfg["me"].get("topics") or [] if str(t).strip()]
    newtxt = "\n".join(f"- {p['name']}: {p['meta'].get('summary', '')} / 결과: " +
                       " ".join(ln[2:] for ln in dict(sections(p['body'])).get('## 📊 주요 결과', '').splitlines() if ln.startswith('- '))[:600]
                       for p in g["new"]) or "(없음)"
    candtxt = "\n".join(f"- id {c['id']} · {c['journal']} · {c['title']} · {c['abstract'][:400]}" for c in g["cands"]) or "(없음)"
    prompt = (read_text(PROMPT).replace("{topics}", "\n".join(f"- {t}" for t in topics) or "(아직 적지 않음: wiki.toml [me] topics)")
              .replace("{new_pages}", newtxt).replace("{candidates}", candtxt))
    try:
        d, _ = codex.run(prompt, SCHEMA, cfg, label="briefing")
        return d, ""
    except codex.CodexError as e:
        return None, str(e)


def render(cfg: dict, g: dict, d: dict | None, err: str) -> str:
    d = d or {}
    rate = {c.get("id"): c for c in d.get("candidates") or []}
    lines_of = {x.get("citekey"): x.get("lines") or [] for x in d.get("new_pages") or []}
    clean_ = lambda s: re.sub(r"\s*—\s*", ", ", str(s or "")).strip()  # noqa: E731
    L = [f"# 오늘의 연구 브리핑 · {TODAY}", ""]
    L += [f"> {clean_(d['headline'])}", ""] if d.get("headline") else []
    if d.get("pick"):
        L += ["## ⭐ 오늘 먼저 읽을 것", "", clean_(d["pick"]), ""]
    L += [f"## 📥 새로 들어온 논문 ({len(g['new'])})", ""]
    for p in g["new"]:
        m = p["meta"]
        L.append(f"### [[{p['name']}]] {m.get('title', '')}")
        L += [f"- {clean_(x)}" for x in lines_of.get(p["name"], [])] or [f"- {m.get('summary', '')}"]
        rel = relation_line(p["body"])
        if rel:
            L.append(f"- 내 연구와의 관계: {rel}")
        L.append("")
    if not g["new"]:
        L += ["새 논문 없음. Zotero의 'Wiki Inbox' 컬렉션에 읽을 논문을 넣거나, 아래 후보를 `wiki add 번호`로 넣는다.", ""]
    cands = sorted(g["cands"], key=lambda c: (-(rate.get(c["id"], {}).get("relevance") or 0), -c["id"]))
    shown = [c for c in cands if (rate.get(c["id"], {}).get("relevance") or 0) > 0 or not rate][: cfg["daily"]["candidates_max"]]
    L += [f"## 🔭 관심 저널 신착 (관련도 순 {len(shown)} / 새로 찾은 {len(g['cands'])})", ""]
    if shown:
        L += ["| 번호 | 관련도 | 학술지 | 논문 | 한 줄 |", "|---|---|---|---|---|"]
        for c in shown:
            r = rate.get(c["id"], {})
            one = clean_(r.get("one_line") or "") + (f" ({clean_(r['why'])})" if r.get("why") else "")
            cell = lambda x: str(x).replace("|", "/").replace("\n", " ")  # noqa: E731
            L.append(f"| {c['id']} | {'★' * int(r.get('relevance') or 0) or '-'} | {cell(c['journal'])} | [{cell(c['title'])}](https://doi.org/{c['doi']}) | {cell(one)} |")
        L += ["", "넣고 싶은 논문은 터미널에서 `wiki add 번호` (여러 개는 `wiki add 3 7`). 다음 실행 때 위키 페이지가 된다.", ""]
    else:
        L += ["새 후보 없음." + ("" if cfg["journals"].get("fields") or cfg["journals"].get("extra") else " (wiki.toml [journals]에 분야를 고르면 신착을 모은다)"), ""]
    if g["pdf_needed"]:
        L += [f"## 📄 PDF가 필요한 논문 ({len(g['pdf_needed'])})", "",
              "초록만으로 쓴 페이지다. PDF를 Zotero 항목에 붙이면 `wiki ingest --key <키> --force`로 본문 기준으로 다시 만든다.", ""]
        L += [f"- [[{p['name']}]] {p['meta'].get('title', '')} · [도서관]({library_link(cfg, str(p['meta'].get('doi', '')))})" for p in g["pdf_needed"][:15]]
        L.append("")
    probs = [f"{v.get('citekey', k)}: {'; '.join(v.get('notes', []))[:160]}" for k, v in g["failed"]]
    probs += [f"신착 수집: {e}" for e in g["collect"].get("errors", [])]
    if err:
        probs.append(f"브리핑 요약: {err} (목록만 표시)")
    if probs:
        L += ["## ⚠️ 확인할 것", ""] + [f"- {x}" for x in probs] + [""]
    L += ["---", f"`wiki daily` · {now()} · 위키 [[index]]"]
    return "\n".join(L) + "\n"


def run(cfg: dict) -> str:
    config.ensure_dirs()
    g = gather(cfg)
    today_file = config.BRIEFINGS / f"{TODAY}.md"
    if today_file.exists() and not (g["new"] or g["cands"]):
        print("오늘 브리핑이 이미 있고 새로 들어온 것이 없어 그대로 둠 (BRIEFING.md)")
        return read_text(today_file)
    d, err = ask_model(cfg, g)
    text = render(cfg, g, d, err)
    write_text(config.BRIEFINGS / f"{TODAY}.md", text)
    write_text(config.BRIEFING, text)
    st = g["state"]
    st["briefed_pages"] = sorted(set(st["briefed_pages"]) | {p["name"] for p in g["new"]})
    st["last"] = now()
    jsave(STATE, st)
    collect.mark([c["id"] for c in g["cands"]], "briefed")
    print(f"브리핑: 새 논문 {len(g['new'])} · 신착 {len(g['cands'])} · PDF 필요 {len(g['pdf_needed'])}" + (f" · {err}" if err else ""))
    return text
