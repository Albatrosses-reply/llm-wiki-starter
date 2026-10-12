"""관심 저널 신착 수집(Crossref, 키 불필요). 후보는 .wiki/candidates.json에 번호를 붙여 쌓고, 브리핑이 보여 준다.
마음에 드는 후보는 `wiki add <번호>`로 Zotero에 넣는다."""
from __future__ import annotations

import json
import re
import time
import tomllib
import urllib.parse
import urllib.request
from datetime import date, timedelta

from . import config, pages
from .util import clean, jload, jsave, norm_doi, now

CANDS = config.STATE / "candidates.json"
STATE = config.STATE / "collect_state.json"
JOURNALS = config.PKG / "data" / "journals.toml"
SKIP_TITLE = re.compile(r"^(editorial board|issue information|front matter|back matter|erratum|errata|correction|corrigendum|"
                        r"table of contents|masthead|reviewer|acknowledg|in this issue|editor'?s note|announcement)", re.I)


def journal_list(cfg: dict) -> list[dict]:
    with open(JOURNALS, "rb") as f:
        lib = tomllib.load(f)
    out, seen = [], set()
    for field in cfg["journals"].get("fields") or []:
        for j in lib.get(field, []):
            if j["issn"] not in seen:
                out.append(j)
                seen.add(j["issn"])
    for j in cfg["journals"].get("extra") or []:
        if j.get("issn") and j["issn"] not in seen:
            out.append({"name": j.get("name", j["issn"]), "issn": j["issn"]})
            seen.add(j["issn"])
    return out


def fields_available() -> list[str]:
    with open(JOURNALS, "rb") as f:
        return list(tomllib.load(f).keys())


def crossref_new(issn: str, since: str, mailto: str, rows: int = 60) -> list[dict]:
    q = urllib.parse.urlencode({"filter": f"from-created-date:{since},type:journal-article", "rows": rows,
                                "select": "DOI,title,author,container-title,created,abstract", "sort": "created", "order": "desc",
                                **({"mailto": mailto} if mailto else {})})
    req = urllib.request.Request(f"https://api.crossref.org/journals/{issn}/works?{q}",
                                 headers={"User-Agent": f"wikikit/0.1 (mailto:{mailto or 'unknown'})"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))["message"]["items"]


def run(cfg: dict) -> dict:
    config.ensure_dirs()
    st = jload(STATE, {})
    since = st.get("last") or (date.today() - timedelta(days=int(cfg["daily"]["lookback_days"]))).isoformat()
    cands = jload(CANDS, {"next_id": 1, "items": []})
    have = {c["doi"] for c in cands["items"]} | {str(p["meta"].get("doi", "")) for p in pages.all_pages()}
    kws = [k.lower() for k in cfg["journals"].get("keywords") or [] if k.strip()]
    added, errors = 0, []
    for j in journal_list(cfg):
        try:
            items = crossref_new(j["issn"], since, cfg["me"].get("email", ""))
        except Exception as e:  # noqa: BLE001
            errors.append(f"{j['name']}: {type(e).__name__}")
            continue
        for m in items:
            doi, title = norm_doi(m.get("DOI")), clean((m.get("title") or [""])[0])
            if not doi or doi in have or not title or SKIP_TITLE.search(title):
                continue
            abstract = clean(re.sub(r"^\s*abstract\s*", "", clean(m.get("abstract")), flags=re.I))
            if kws and not any(k in (title + " " + abstract).lower() for k in kws):
                continue
            cands["items"].append({"id": cands["next_id"], "doi": doi, "title": title, "journal": j["name"],
                                   "authors": [f"{a.get('family', '')}" for a in (m.get("author") or [])][:4],
                                   "abstract": abstract[:1200], "found": now(), "status": "new"})
            cands["next_id"] += 1
            have.add(doi)
            added += 1
        time.sleep(0.2)   # Crossref 예의
    cands["items"] = cands["items"][-500:]
    jsave(CANDS, cands)
    jsave(STATE, {"last": date.today().isoformat(), "at": now(), "errors": errors})
    print(f"신착 후보 {added}편 추가 (저널 {len(journal_list(cfg))}개, {since} 이후)" + (f" · 오류 {len(errors)}" if errors else ""))
    return {"added": added, "errors": errors}


def fresh(limit: int = 40) -> list[dict]:
    """아직 브리핑에 안 나온 후보(최신 순)."""
    return [c for c in reversed(jload(CANDS, {"items": []})["items"]) if c["status"] == "new"][:limit]


def mark(ids: list[int], status: str) -> None:
    cands = jload(CANDS, {"next_id": 1, "items": []})
    for c in cands["items"]:
        if c["id"] in ids:
            c["status"] = status
    jsave(CANDS, cands)


def find(cid: int) -> dict | None:
    return next((c for c in jload(CANDS, {"items": []})["items"] if c["id"] == cid), None)
