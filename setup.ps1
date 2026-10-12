# LLM Wiki 스타터 설치 (Windows)
# 실행: 이 폴더에서 setup.ps1 우클릭 > "PowerShell에서 실행"
# 막히면 PowerShell을 열고:  powershell -ExecutionPolicy Bypass -File .\setup.ps1
param([switch]$DryRun)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"
Set-Location -LiteralPath $PSScriptRoot

function Step($m) { Write-Host "`n== $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "  OK  $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  !!  $m" -ForegroundColor Yellow }
function Stop-Setup($m) {
  Write-Host "`n  XX  $m" -ForegroundColor Red
  if (-not $DryRun) { Read-Host "엔터를 누르면 닫힙니다" | Out-Null }
  exit 1
}

Step "1/6 위치 점검"
if ($PSScriptRoot -match 'OneDrive|Google Drive|GoogleDrive|iCloud|Dropbox') {
  Stop-Setup "이 폴더가 클라우드 동기화 폴더 안에 있습니다: $PSScriptRoot`n      C:\Users\$env:USERNAME\llm-wiki 처럼 동기화 밖으로 폴더를 옮긴 뒤 다시 실행하세요."
}
Ok $PSScriptRoot

Step "2/6 필요한 프로그램"
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  if ($DryRun) { Warn "uv 없음 (DryRun: 설치 건너뜀)" } else {
    Write-Host "  uv(파이썬 관리 도구)를 설치합니다..."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
      winget install --id=astral-sh.uv -e --accept-source-agreements --accept-package-agreements | Out-Null
    } else {
      powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
    }
    $env:Path = "$env:USERPROFILE\.local\bin;$env:LOCALAPPDATA\Microsoft\WinGet\Links;$env:Path"
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { Stop-Setup "uv 설치 확인 실패. PowerShell을 새로 열고 다시 실행하세요." }
  }
}
if (Get-Command uv -ErrorAction SilentlyContinue) { Ok "uv" }
if (Get-Command codex -ErrorAction SilentlyContinue) { Ok "Codex CLI" } else {
  Warn "Codex CLI가 없습니다. Node.js(nodejs.org, LTS)를 설치한 뒤 PowerShell에서:  npm install -g @openai/codex  그리고  codex login"
}
if (Get-Command git -ErrorAction SilentlyContinue) { Ok "git" } else { Warn "git 없음 (없어도 동작합니다. 변경 기록을 남기려면 git-scm.com)" }

Step "3/6 파이썬 환경 (.venv)"
if ($DryRun) { Warn "DryRun: 건너뜀" } else {
  uv venv --python 3.12 .venv
  if ($LASTEXITCODE -ne 0) { Stop-Setup "파이썬 환경을 만들지 못했습니다." }
  uv pip install --python .venv\Scripts\python.exe -e . --quiet
  if ($LASTEXITCODE -ne 0) { Stop-Setup "패키지 설치 실패." }
  Ok "wikikit 설치"
}

Step "4/6 설정 (질문 4개)"
if ($DryRun) { Warn "DryRun: 건너뜀" } else { & .\wiki.cmd init }

Step "5/6 점검"
if ($DryRun) { Warn "DryRun: 건너뜀" } else { & .\wiki.cmd doctor }

Step "6/6 매일 자동 실행"
if ($DryRun) { Warn "DryRun: 건너뜀"; exit 0 }
if ((Get-Command git -ErrorAction SilentlyContinue) -and -not (Test-Path .git)) { git init -q; Ok "git 기록 시작" }
$a = Read-Host "매일 08:00(놓치면 PC를 켤 때)에 수집·요약·브리핑을 자동으로 돌릴까요? [Y/n]"
if ($a -ne "n" -and $a -ne "N") { & .\wiki.cmd schedule on }

$b = Read-Host "지금 한 번 돌려서 첫 브리핑을 만들까요? (Zotero가 켜져 있어야 합니다, 몇 분 걸림) [Y/n]"
if ($b -ne "n" -and $b -ne "N") {
  & .\wiki.cmd daily
  if (Test-Path BRIEFING.md) { Invoke-Item BRIEFING.md }
}
Write-Host "`n끝났습니다. README의 '매일 쓰는 법'을 보세요." -ForegroundColor Green
Read-Host "엔터를 누르면 닫힙니다" | Out-Null
