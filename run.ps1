# 키스토 백엔드 + 바탕화면 위젯을 한 번에 띄운다. (run.cmd 더블클릭으로도 실행 가능)
#   -BackendOnly : 위젯 없이 백엔드만 띄운다
#   -Lab         : 위젯과 함께 연구실 창도 바로 연다
param([switch]$BackendOnly, [switch]$Lab)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$api = "http://127.0.0.1:8420"

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
  throw "가상환경이 없습니다. 먼저: python -m venv .venv ; .venv\Scripts\pip install -r requirements.txt"
}

# claude CLI(하네스)가 PATH에 없으면 Claude 데스크톱 앱에 번들된 것을 찾아 이 프로세스에만 추가한다.
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
  $found = @(
    Get-ChildItem "$env:LOCALAPPDATA\Packages\Claude_*\LocalCache\Roaming\Claude\claude-code\*\claude.exe" -ErrorAction SilentlyContinue
    Get-ChildItem "$env:APPDATA\Claude\claude-code\*\claude.exe" -ErrorAction SilentlyContinue
  ) | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if ($found) { $env:PATH = "$($found.DirectoryName);$env:PATH" }
}

# Node.js도 PATH에 없으면 흔한 설치 위치에서 찾는다.
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  foreach ($dir in @("$env:USERPROFILE\nodejs", "$env:ProgramFiles\nodejs")) {
    if (Test-Path "$dir\npm.cmd") { $env:PATH = "$dir;$env:PATH"; break }
  }
}

function Get-Health {
  try { Invoke-RestMethod "$api/health" -TimeoutSec 2 } catch { $null }
}

$health = Get-Health
if (-not $health) {
  $data = Join-Path $root "data"
  New-Item -ItemType Directory -Force $data | Out-Null
  $log = Join-Path $data "backend.log"
  Write-Host "백엔드를 띄우는 중..."
  Start-Process -FilePath $python -ArgumentList "-m", "uvicorn", "main:app", "--port", "8420" `
    -WorkingDirectory (Join-Path $root "backend") -WindowStyle Hidden `
    -RedirectStandardOutput $log -RedirectStandardError "$log.err"
  for ($i = 0; $i -lt 40 -and -not $health; $i++) {
    Start-Sleep -Seconds 1
    $health = Get-Health
  }
  if (-not $health) { throw "백엔드가 뜨지 않았습니다. $log.err 를 확인하세요." }
}
Write-Host "백엔드 준비 완료 — provider: $($health.providers -join ', ')"

if ($BackendOnly) { return }

$widget = Join-Path $root "widget"
if (-not (Test-Path "$widget\node_modules\electron")) {
  Push-Location $widget
  npm install
  Pop-Location
}
$electronArgs = @("`"$widget`"")
if ($Lab) { $electronArgs += "--lab" }
Start-Process -FilePath "$widget\node_modules\electron\dist\electron.exe" -ArgumentList $electronArgs -WorkingDirectory $widget
Write-Host "위젯 실행 — 트레이 아이콘 또는 Ctrl+Shift+K로 보이기/숨기기, 🏠 버튼으로 연구실"
