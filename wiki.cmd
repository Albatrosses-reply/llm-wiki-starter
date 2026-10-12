@echo off
rem wiki command for Windows. Example: wiki.cmd doctor, wiki.cmd add 3
setlocal
set PYTHONUTF8=1
"%~dp0.venv\Scripts\python.exe" -m wikikit %*
