# hwpx 파일을 설치된 한글(HWPFrame.HwpObject, COM 자동화)로 열어 쪽수를 확인하고 PDF로 내보낸다.
# 생성한 신청서가 한글에서 실제로 열리는지 확인하는 용도 (XML이 올바르기만 해서는 안 열릴 수 있다 —
# 예: header.xml의 secCnt가 실제 구역 수와 다르면 열기에 실패한다).
#
#   powershell -ExecutionPolicy Bypass -File scripts\check_hwpx.ps1 docs\KISTO_AIX_신청서.hwpx [출력.pdf]
param(
  [Parameter(Mandatory = $true)][string]$Path,
  [string]$Pdf
)
$ErrorActionPreference = "Stop"
$full = (Resolve-Path $Path).Path
if (-not $Pdf) { $Pdf = [IO.Path]::ChangeExtension($full, ".pdf") }

$hwp = New-Object -ComObject HWPFrame.HwpObject
try { $hwp.XHwpWindows.Item(0).Visible = $false } catch {}
try {
  $ok = $hwp.Open($full, "HWPX", "forceopen:true;versionwarning:false")
  if (-not $ok) { throw "한글이 파일을 열지 못했습니다: $full" }
  Write-Host "열기 성공 — $($hwp.PageCount)쪽"
  if ($hwp.SaveAs($Pdf, "PDF", "")) { Write-Host "PDF 저장: $Pdf" }
} finally {
  $hwp.Clear(1)
  $hwp.Quit()
}
