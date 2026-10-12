@echo off
rem wiki 명령 (Windows). 예: wiki doctor, wiki add 3
setlocal
set PYTHONUTF8=1
"%~dp0.venv\Scripts\python.exe" -m wikikit %*
