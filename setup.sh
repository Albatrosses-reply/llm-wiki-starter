#!/usr/bin/env bash
# LLM Wiki 스타터 설치 (macOS·Linux).  실행: ./setup.sh
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONUTF8=1
step() { printf '\n== %s\n' "$1"; }
case "$PWD" in
  *CloudStorage*|*"Mobile Documents"*|*OneDrive*|*Dropbox*)
    echo "이 폴더가 클라우드 동기화 폴더 안에 있습니다: $PWD"; echo "~/llm-wiki 처럼 동기화 밖으로 옮긴 뒤 다시 실행하세요."; exit 1;;
esac
case "$PWD" in
  "$HOME/Documents"*|"$HOME/Desktop"*|"$HOME/Downloads"*)
    echo "!! 문서·데스크탑·다운로드 폴더는 macOS가 자동 실행의 접근을 막을 수 있습니다. ~/llm-wiki 를 권합니다.";;
esac
step "1/5 필요한 프로그램"
command -v uv >/dev/null || { echo "uv 설치..."; curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH="$HOME/.local/bin:$PATH"; }
command -v codex >/dev/null && echo "  OK Codex CLI" || echo "  !! Codex CLI 없음: npm install -g @openai/codex (또는 brew install codex) 후 codex login"
step "2/5 파이썬 환경"
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e . --quiet
chmod +x wiki.sh
step "3/5 설정"
./wiki.sh init
step "4/5 점검"
./wiki.sh doctor || true
step "5/5 매일 자동 실행"
command -v git >/dev/null && [ ! -d .git ] && git init -q && echo "  git 기록 시작"
read -r -p "매일 08:00에 자동으로 돌릴까요? [Y/n] " a
[ "${a:-Y}" != "n" ] && ./wiki.sh schedule on
read -r -p "지금 한 번 돌려서 첫 브리핑을 만들까요? [Y/n] " b
[ "${b:-Y}" != "n" ] && ./wiki.sh daily && echo "→ BRIEFING.md"
