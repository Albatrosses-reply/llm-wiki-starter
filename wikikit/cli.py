"""명령: wiki <하위명령>. 학생이 주로 쓰는 것은 daily(자동), add, doctor 세 가지다."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

from . import __version__, briefing, collect, config, daily, doctor, ingest, pages, schedule, zotero
from .util import norm_doi

HELP = """명령
  wiki doctor              설치 점검 (문제와 고치는 방법)
  wiki init                설정 질문 4개로 wiki.toml 만들기
  wiki daily               수집 → ingest → 브리핑 → 색인 (매일 자동으로 도는 것)
  wiki add 3 7             브리핑의 신착 후보 번호(또는 DOI)를 Zotero에 넣기 → 다음 실행 때 위키 페이지
  wiki ingest [--max N]    Zotero 'Wiki Inbox'의 새 논문을 지금 위키로 (--key 키 --force 로 다시 만들기)
  wiki collect             관심 저널 신착만 모으기
  wiki briefing            브리핑만 다시 쓰기 (BRIEFING.md)
  wiki index               index.md 다시 만들기
  wiki schedule on|off|status   매일 자동 실행 등록·해제·상태
"""


def _ask(q: str, default: str = "") -> str:
    try:
        a = input(f"{q}{f' [{default}]' if default else ''}: ").strip()
    except EOFError:
        a = ""
    return a or default


def init(args) -> int:
    import tomli_w
    cfg = config.load()
    if config.CFG_FILE.exists() and not args.force:
        print(f"이미 있음: {config.CFG_FILE} (다시 만들려면 wiki init --force)")
        return 0
    print("설정 질문 4개입니다. 나중에 wiki.toml을 메모장으로 고쳐도 됩니다.\n")
    cfg["me"]["name"] = _ask("1) 이름", cfg["me"]["name"])
    cfg["me"]["email"] = _ask("2) 이메일 (Crossref에 예의상 알리는 연락처, 공개되지 않음)", cfg["me"]["email"])
    print("3) 연구 주제를 한 줄씩, 최대 3줄 (빈 줄이면 끝). 예: 스테이블코인 런 위험과 보유자 구조")
    topics = []
    while len(topics) < 3:
        t = _ask(f"   주제 {len(topics) + 1}")
        if not t:
            break
        topics.append(t)
    cfg["me"]["topics"] = topics
    fields = collect.fields_available()
    print("4) 신착을 받아 볼 분야 번호 (여러 개는 쉼표):  " + "  ".join(f"{i}. {f}" for i, f in enumerate(fields, 1)))
    picks = [x.strip() for x in _ask("   번호", "1").split(",")]
    cfg["journals"]["fields"] = [fields[int(x) - 1] for x in picks if x.isdigit() and 1 <= int(x) <= len(fields)]
    with open(config.CFG_FILE, "wb") as f:
        tomli_w.dump(cfg, f)
    print(f"\n저장: {config.CFG_FILE}")
    return 0


def add(args) -> int:
    cfg = config.load()
    if not zotero.launch(cfg):
        print("Zotero가 응답하지 않습니다. Zotero를 켜고 다시.")
        return 1
    items, ids = [], []
    for x in args.what:
        if x.isdigit():
            c = collect.find(int(x))
            if not c:
                print(f"후보 {x}번 없음")
                continue
            doi = c["doi"]
            ids.append(int(x))
        else:
            doi = norm_doi(x)
        try:
            req = urllib.request.Request(f"https://api.crossref.org/works/{doi}", headers={"User-Agent": "wikikit/0.1"})
            with urllib.request.urlopen(req, timeout=30) as r:
                msg = json.loads(r.read().decode("utf-8"))["message"]
        except Exception as e:  # noqa: BLE001
            print(f"{doi}: Crossref 조회 실패({type(e).__name__})")
            continue
        items.append(zotero.crossref_to_item(msg, cfg["zotero"]["inbox_tag"]))
        print(f"+ {items[-1].get('title', doi)[:90]}")
    if not items:
        return 1
    ok, err = zotero.save_items(cfg, items)
    if ok:
        collect.mark(ids, "added")
        print(f"Zotero에 {len(items)}편 저장(태그 '{cfg['zotero']['inbox_tag']}'). PDF는 Zotero에서 항목 우클릭 › '사용 가능한 PDF 찾기' "
              "또는 학교 도서관에서 받아 끌어다 놓으면 본문으로 요약한다. 다음 `wiki daily`(또는 지금 `wiki ingest`)에 위키 페이지가 된다.")
        return 0
    print(f"저장 실패: {err}")
    return 1


def main(argv: list[str] | None = None) -> int:
    os.environ.setdefault("PYTHONUTF8", "1")
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")   # Windows 콘솔에서 한글이 깨지지 않게
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="wiki", description=f"wikikit {__version__}", epilog=HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("doctor")
    p = sub.add_parser("init")
    p.add_argument("--force", action="store_true")
    sub.add_parser("daily")
    p = sub.add_parser("add")
    p.add_argument("what", nargs="+")
    p = sub.add_parser("ingest")
    p.add_argument("--max", type=int)
    p.add_argument("--key", nargs="*")
    p.add_argument("--force", action="store_true")
    sub.add_parser("collect")
    sub.add_parser("briefing")
    sub.add_parser("index")
    p = sub.add_parser("schedule")
    p.add_argument("action", choices=["on", "off", "status"])
    args = ap.parse_args(argv)
    cfg = config.load()
    if args.cmd == "doctor":
        return doctor.run(cfg)
    if args.cmd == "init":
        return init(args)
    if args.cmd == "daily":
        return daily.run(cfg)
    if args.cmd == "add":
        return add(args)
    if args.cmd == "ingest":
        res = ingest.run(cfg, args.max, args.key, args.force)
        return 0 if all(r["ok"] for r in res) else 1
    if args.cmd == "collect":
        collect.run(cfg)
        return 0
    if args.cmd == "briefing":
        briefing.run(cfg)
        print(f"→ {config.BRIEFING}")
        return 0
    if args.cmd == "index":
        print(f"index.md: {pages.build_index()}편")
        return 0
    if args.cmd == "schedule":
        print({"on": lambda: schedule.on(cfg), "off": schedule.off, "status": schedule.status}[args.action]())
        return 0
    ap.print_help()
    return 0
