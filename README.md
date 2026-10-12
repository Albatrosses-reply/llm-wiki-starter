# LLM Wiki 스타터

읽을 논문을 Zotero에 넣으면, 다음 날 아침 **한국어 연구 브리핑**과 **논문별 위키 페이지**가 생깁니다.
요약은 각자의 ChatGPT 구독으로 돌아가는 **Codex CLI**가 쓰고, 서지 정보는 언제나 Zotero 값을 씁니다.

```
Zotero 'Wiki Inbox'에 논문 넣기 ─┐
관심 저널 신착(자동 수집) ───────┼─▶ 매일 08:00 자동 실행 ─▶ BRIEFING.md (오늘 들어온 논문 3줄 요약,
                                  │                              관련도 순 신착 후보, 먼저 읽을 것)
`wiki add 3` (후보 번호로 추가) ──┘                           ─▶ notes/sources/<논문>.md (요약·방법·결과·한계·초안)
```

> 이 저장소는 초안입니다. 1차 목표는 "논문이 잘 들어오고 아침에 브리핑을 받는 것"입니다. 쓰면서 함께 발전시킵니다.

---

## 1. 준비물

| 무엇 | 왜 | 받는 곳 |
|---|---|---|
| Windows 10/11 (macOS도 됨) | | |
| **Zotero 7** | 논문 서지와 PDF의 정답 | zotero.org |
| Zotero 브라우저 커넥터 | 웹에서 논문을 한 번에 저장 | zotero.org/download |
| **ChatGPT 구독** (Plus 이상) | Codex 사용 | |
| **Node.js LTS** | Codex CLI 설치에 필요 | nodejs.org |
| Obsidian (권장) | 위키를 보기 좋게 읽기, 링크 따라가기 | obsidian.md |
| Better BibTeX (선택) | 논문 키를 `AuthorEtAl2024` 형식으로 통일 | retorque.re/zotero-better-bibtex |

## 2. 설치 (약 15분)

**① 내려받아 풀기**
GitHub 페이지의 초록색 **Code › Download ZIP**을 누르고, `C:\Users\<내 이름>\llm-wiki` 에 풉니다.
⚠️ **OneDrive·Google Drive·iCloud 폴더 안에 두지 마세요.** 동기화 프로그램이 파일을 잠가서 자동 실행이 실패합니다.

**② Zotero 설정 두 가지**
1. Zotero › 편집 › 설정 › 고급 › **"이 컴퓨터의 다른 애플리케이션이 Zotero와 통신하도록 허용"** 체크
2. 왼쪽 "내 라이브러리"에서 우클릭 › 새 컬렉션 › 이름 **`Wiki Inbox`**

**③ Codex CLI**
PowerShell을 열고:
```powershell
npm install -g @openai/codex
codex login
```
브라우저가 열리면 ChatGPT 계정으로 로그인합니다.

**④ 설치 실행**
`llm-wiki` 폴더에서 **`setup.ps1` 우클릭 › PowerShell에서 실행**.
(막히면 PowerShell에서 `cd $HOME\llm-wiki` 후 `powershell -ExecutionPolicy Bypass -File .\setup.ps1`)

설치가 묻는 것: 이름, 이메일, **연구 주제 1~3줄**, 신착을 받을 분야(정보시스템·재무·경영·경제).
마지막에 "매일 자동 실행"과 "지금 첫 브리핑 만들기"를 물으면 Enter(예)를 누릅니다.

macOS는 터미널에서 `./setup.sh`.

## 3. 매일 쓰는 법

**논문 넣기 (둘 중 편한 것)**
- 브라우저에서 논문 페이지를 열고 Zotero 커넥터로 **`Wiki Inbox` 컬렉션에 저장** (PDF가 같이 저장되면 본문으로 요약합니다)
- 브리핑의 신착 후보를 번호로: `.\wiki.cmd add 3 7`

**아침에 보기**: `BRIEFING.md` (Obsidian에서 `llm-wiki` 폴더를 보관함으로 열면 링크가 바로 이어집니다)

**초안 고치기**: 논문 페이지의 ✍️ Contribution · ⚠️ Caveats · 🧭 내 연구와의 관계는 **자동 초안**입니다.
고쳐 쓰고 바로 위의 `<!-- llm-draft ... -->` 줄을 지우면 그 섹션은 내 것이 되어 자동화가 다시 건드리지 않습니다.

**Codex에게 묻기**: 폴더에서 `codex`를 열고
- "스테이블코인 런 관련해서 위키에 뭐가 있어?"
- "브리핑 다시 만들어줘", "후보 3번 넣어줘"

## 4. 명령 (Windows `.\wiki.cmd …`, macOS `./wiki.sh …`)

| 명령 | 하는 일 |
|---|---|
| `wiki doctor` | 설치 점검. 문제와 고치는 방법 (도움 요청할 때 이 출력을 보내 주세요) |
| `wiki daily` | 수집 → 위키 만들기 → 브리핑 (매일 자동으로 도는 것) |
| `wiki add 3 7` / `wiki add 10.1287/...` | 후보 번호나 DOI를 Zotero에 넣기 |
| `wiki ingest` | Inbox의 새 논문을 지금 위키로 |
| `wiki ingest --key <키> --force` | PDF를 붙인 뒤 페이지를 본문 기준으로 다시 |
| `wiki briefing` | 브리핑만 다시 |
| `wiki schedule on / off / status` | 매일 자동 실행 켜기·끄기·상태 |

## 5. 설정 `wiki.toml` (메모장으로 고침)

- `[me] topics`: 연구 주제. 신착 관련도와 "내 연구와의 관계"가 이걸 봅니다. **구체적으로 쓸수록 좋습니다.**
- `[journals] fields`, `extra`, `keywords`: 신착을 받을 저널과 걸러낼 단어
- `[daily] ingest_max`: 하루에 위키로 만들 논문 수(기본 3). ChatGPT 요금제의 Codex 사용 한도를 생각해 작게 시작하세요
- `[library]`: 학교 도서관 프록시·EBSCO 주소를 넣으면 "PDF가 필요한 논문"에 도서관 링크가 붙습니다
- 내 원고를 연결하려면 `notes/projects/_예시-내-원고.md`를 복사해 `p-짧은이름.md`로 채우세요

## 6. 문제 해결

| 증상 | 해결 |
|---|---|
| setup.ps1이 바로 닫힘 | PowerShell에서 `powershell -ExecutionPolicy Bypass -File .\setup.ps1` |
| doctor: "Zotero 로컬 API 꺼짐" | 2-② 설정 |
| 브리핑에 "Codex 사용 한도" | 그날 한도를 다 썼습니다. 다음 날 자동으로 이어집니다. `ingest_max`를 줄이세요 |
| 아침에 브리핑이 안 생김 | `wiki schedule status`, `.wiki\daily.log` 확인. PC가 꺼져 있었다면 켤 때 실행됩니다 |
| 페이지가 "초록만(PDF 없음)" | Zotero에서 그 항목에 PDF를 붙이고 `wiki ingest --key <키> --force` |

## 7. 알아 둘 것

- **어디로 무엇이 가나**: 논문의 초록과 PDF 앞부분·결론 일부가 요약을 위해 Codex(OpenAI)로 갑니다. 그 밖의 위키는 내 PC에만 있습니다. 미공개 원고를 Inbox에 넣을 때는 이 점을 생각하세요.
- **PDF**: 유료 논문 PDF를 자동으로 내려받지 않습니다(출판사 약관). 도서관에서 직접 받아 Zotero 항목에 끌어다 놓으세요.
- **Zotero 데이터**: 이 프로그램은 Zotero 데이터베이스를 직접 고치지 않습니다. 새 항목 추가(`wiki add`)만 Zotero 커넥터로 합니다.
- **초안은 초안**: 자동 요약은 틀릴 수 있습니다. 인용문은 PDF에 실제로 있는 문장만 남기지만, 해석은 반드시 원문으로 확인하세요.

## 8. 앞으로 (함께 정할 것)

논문 간 관계(확장·반박) 제안, 인용 그래프, 주간 정리, 연구실 공유 위키.

## 라이선스

코드 MIT. `LICENSE` 참조.
