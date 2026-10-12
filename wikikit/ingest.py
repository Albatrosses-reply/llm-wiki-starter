"""ingest: Zotero 'Wiki Inbox'의 논문을 위키 source 페이지로. 편마다 codex exec 한 번."""
from __future__ import annotations

from pathlib import Path

from . import codex, config, pages, pdf, zotero
from .util import TODAY, jload, jsave, now, read_text, write_text

PROMPT = config.PKG / "prompts" / "ingest.md"
RULES = config.PKG / "prompts" / "human_rules.md"
SCHEMA = config.PKG / "schemas" / "ingest.schema.json"
STATE = config.STATE / "ingest_state.json"
MAX_TRIES = 3


def targets(cfg: dict, keys: list[str] | None = None, force: bool = False) -> list[dict]:
    """아직 위키 페이지가 없는 Inbox 항목. keys(Zotero 키·citekey·DOI)를 주면 그것만, force면 페이지가 있어도 다시."""
    known = pages.known_zotero_keys()
    st = jload(STATE, {})
    want = {k.lower() for k in keys or []}
    out = []
    for it in zotero.inbox_items(cfg):
        d = it.get("data") or {}
        ids = {it["key"].lower(), str(d.get("citationKey", "")).lower(), zotero.doi_of(d)}
        if want:
            if not ids & want or (it["key"] in known and not force):
                continue
        elif it["key"] in known or st.get(it["key"], {}).get("tries", 0) >= MAX_TRIES:
            continue
        out.append(it)
    return sorted(out, key=lambda it: (it.get("data") or {}).get("dateAdded", ""))


def build_prompt(cfg: dict, b: dict, texts: list[str], chosen: list[int]) -> str:
    topics = [t for t in cfg["me"].get("topics") or [] if str(t).strip()]
    proj, _ = pages.project_digest()
    return (read_text(PROMPT)
            .replace("{title}", b["title"]).replace("{authors}", "; ".join(b["authors"]) or "(없음)")
            .replace("{year}", str(b["year"] or "")).replace("{venue}", b["venue"] or "").replace("{doi}", b["doi"] or "(없음)")
            .replace("{abstract}", b["abstract"] or "(Zotero에 초록 없음)")
            .replace("{topics}", "\n".join(f"- topic-{i}: {t}" for i, t in enumerate(topics, 1)) or "(아직 적지 않음)")
            .replace("{projects}", proj).replace("{concepts}", pages.concept_digest()).replace("{rules}", read_text(RULES))
            .replace("{pdf_note}", f"PDF {len(texts)}쪽 중 {', '.join(map(str, chosen))}쪽" if chosen else "PDF 없음, 초록만")
            .replace("{pdf_text}", pdf.excerpt(texts, chosen) if chosen else "(PDF 없음)"))


def ingest_one(cfg: dict, it: dict) -> dict:
    taken = {p["name"].lower() for p in pages.all_pages()}
    b = zotero.bib(cfg, it, taken)
    res = {"zotero_key": it["key"], "citekey": b["citekey"], "title": b["title"][:80], "ok": False, "notes": []}
    texts, chosen = [], []
    if b["pdf_path"]:
        try:
            texts = pdf.pages(Path(b["pdf_path"]))
            chosen = pdf.pick(texts)
        except Exception as e:  # noqa: BLE001
            res["notes"].append(f"PDF를 읽지 못함({type(e).__name__}), 초록만으로")
    try:
        d, info = codex.run(build_prompt(cfg, b, texts, chosen), SCHEMA, cfg, label=f"ingest-{b['citekey']}")
    except codex.CodexError as e:
        res["notes"].append(str(e))
        return res
    _, project_slugs = pages.project_digest()
    concept_slugs = pages.upsert_concepts(d.get("concepts") or [], b["citekey"])
    text, notes = pages.render_source(b, d, cfg, chosen, texts, project_slugs, concept_slugs)
    path = pages.page_path(b["citekey"])
    if path.exists():
        text = pages.keep_human_sections(read_text(path), text)
    write_text(path, text)
    res.update(ok=True, notes=res["notes"] + notes, pdf=bool(chosen), **info)
    return res


def run(cfg: dict, max_n: int | None = None, keys: list[str] | None = None, force: bool = False) -> list[dict]:
    config.ensure_dirs()
    if not zotero.launch(cfg):
        return [{"ok": False, "citekey": "-", "notes": ["Zotero가 응답하지 않음(실행 중인지, 로컬 API가 켜졌는지 확인)"]}]
    todo = targets(cfg, keys, force)[: (max_n if max_n is not None else cfg["daily"]["ingest_max"])]
    st, results = jload(STATE, {}), []
    for it in todo:
        r = ingest_one(cfg, it)
        rec = st.setdefault(it["key"], {"tries": 0})
        rec.update(tries=0 if r["ok"] else rec.get("tries", 0) + 1, last=now(), citekey=r["citekey"], ok=r["ok"], notes=r["notes"][:3])
        jsave(STATE, st)
        results.append(r)
        print(f"{'✓' if r['ok'] else '✗'} {r['citekey']} · {r['title']} · {'; '.join(r['notes']) or 'ok'}")
    if any(r["ok"] for r in results):
        pages.build_index()
        pages.log("ingest", [f"[[{r['citekey']}]] {r['title']}" for r in results if r["ok"]])
    jsave(config.STATE / "last_ingest.json", {"date": TODAY, "results": results})
    return results
