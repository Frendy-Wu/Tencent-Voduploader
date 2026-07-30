$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Test-Path -LiteralPath ".venv")) {
    python -m venv .venv
}

& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
& ".\.venv\Scripts\pyinstaller.exe" `
    --noconfirm `
    --clean `
    --windowed `
    --onefile `
    --name "LiuguangVODUploader" `
    --collect-all tkinterdnd2 `
    --collect-all qcloud_vod `
    app.py

Write-Host ""
Write-Host "Build complete: $PSScriptRoot\dist\LiuguangVODUploader.exe"
