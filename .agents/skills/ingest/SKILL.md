---
name: ingest
description: Zotero의 논문(Wiki Inbox 컬렉션, DOI, 브리핑 후보 번호)을 위키 source 페이지로 만든다. "이 논문 넣어줘", "새 논문 처리", "후보 N번 넣어줘"에 쓴다.
---

1. 사람이 DOI나 후보 번호를 주면 먼저 `wiki add <DOI 또는 번호>`로 Zotero에 넣는다(Windows `.\wiki.cmd`, macOS `./wiki.sh`).
2. `wiki ingest`를 실행한다. 특정 논문만이면 `wiki ingest --key <Zotero키 또는 citekey 또는 DOI>`, 이미 있는 페이지를 PDF가 생겨서 다시 만들면 `--force`.
3. 출력의 ✓/✗ 줄을 보고 결과를 한국어로 짧게 알린다: 만든 페이지(`notes/sources/<citekey>.md`), PDF 없이 초록만으로 만든 것, 실패와 이유.
4. 초록만으로 만든 페이지가 있으면 "Zotero에서 그 항목에 PDF를 붙인 뒤 `wiki ingest --key <키> --force`"라고 안내한다.
5. 페이지를 직접 고쳐 쓰지 않는다. 내용이 이상하면 어디가 이상한지 사람에게 보여 주고, 사람이 원하면 그 부분만 고친다(사람 섹션은 표식 규칙을 지킨다).
