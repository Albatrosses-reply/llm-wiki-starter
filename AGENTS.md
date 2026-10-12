# LLM Wiki 운영 규약 (Codex용)

이 폴더는 한 대학원생의 연구 문헌 위키다. **Zotero가 서지의 정답**이고, 위키는 읽은 논문의 요약·해석·연결을 쌓는다.
너(Codex)는 사서다. 요약 초안, 연결, 색인, 브리핑을 맡는다. 무엇이 중요한지 판단하는 글은 사람이 최종으로 쓴다.

## 폴더
| 위치 | 내용 |
|---|---|
| `notes/sources/<citekey>.md` | 논문 1편 = 1페이지 |
| `notes/concepts/<slug>.md` | 개념·방법·데이터 |
| `notes/projects/p-<이름>.md` | 내 원고(사람이 만든다) |
| `BRIEFING.md`, `reports/briefing/` | 아침 브리핑 |
| `index.md` | 전체 색인. 무엇을 찾든 여기서 시작 |
| `wikikit/` | 프로그램. 고치지 않는다 |
| `.wiki/` | 상태·로그(사람이 볼 필요 없음) |

## 규칙
1. 서지(title·authors·year·venue·doi·citekey)는 Zotero 값만 쓴다. 고치지 않는다.
2. 사람 섹션(✍️ Contribution · ⚠️ Caveats · 🧭 내 연구와의 관계)은 `<!-- llm-draft ... -->` 표식을 단 초안으로만 쓴다. 표식이 없는 사람 섹션은 사람이 쓴 것이므로 사람이 시키지 않는 한 고치지 않는다.
3. 사실 주장에는 근거를 단다: `(PDF p.N)`, `(초록)`, 다른 페이지는 `[[citekey]]`.
4. 볼트 전체를 훑지 않는다. `index.md` → 필요한 페이지 → 필요하면 그 폴더만 검색.
5. Zotero 데이터 폴더와 데이터베이스는 건드리지 않는다. 새 논문은 `wiki add`로만 넣는다.
6. 유료 PDF를 자동으로 내려받지 않는다. 도서관 링크를 알려 주는 데까지만.
7. 한국어로 쓴다. 논문 제목·고유명사·통계 용어는 원문. em dash(—)와 과장 형용사를 쓰지 않는다.

## 할 일과 명령 (Windows는 `.\wiki.cmd`, macOS는 `./wiki.sh`)
| 사람이 하는 말 | 하는 일 |
|---|---|
| "이 논문 위키에 넣어줘" (DOI) | `wiki add <DOI>` → `wiki ingest` |
| "새 논문 처리해줘" | `wiki ingest` |
| "브리핑 다시 만들어줘" | `wiki collect` → `wiki briefing`, 그리고 `BRIEFING.md` 요약 |
| "후보 3번 넣어줘" | `wiki add 3` |
| "OO에 대해 위키에 뭐가 있어?" | `index.md` → 관련 페이지 3~10개를 읽고 근거 링크를 단 답. 사람이 "저장"이라고 하면 `notes/concepts/`나 새 페이지로 |
| "설치가 이상해" | `wiki doctor` 출력을 보고 고치는 방법 안내 |

자세한 절차는 `.agents/skills/`에 있다.
