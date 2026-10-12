#!/usr/bin/env bash
# wiki 명령 (macOS·Linux). 예: ./wiki.sh doctor, ./wiki.sh add 3
DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHONUTF8=1 exec "$DIR/.venv/bin/python" -m wikikit "$@"
