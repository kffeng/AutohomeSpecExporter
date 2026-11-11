# ASCII-only script: safe for Windows PowerShell 5.1 and PowerShell 7.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Assert-LastExitCode([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

Write-Host "==> Check Python" -ForegroundColor Cyan
$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
    throw "Python was not found. Install 64-bit Python 3.11 and add it to PATH."
}

$Venv = Join-Path $Root ".build-venv"
if (-not (Test-Path $Venv)) {
    python -m venv $Venv
    Assert-LastExitCode "Create virtual environment"
}
$VenvPython = Join-Path $Venv "Scripts\python.exe"

Write-Host "==> Install build dependencies" -ForegroundColor Cyan
& $VenvPython -m pip install --upgrade pip
Assert-LastExitCode "Upgrade pip"
& $VenvPython -m pip install -r (Join-Path $Root "requirements-build.txt")
Assert-LastExitCode "Install build dependencies"

Write-Host "==> Embed web assets" -ForegroundColor Cyan
& $VenvPython (Join-Path $Root "packaging\embed_web_assets.py")
Assert-LastExitCode "Embed web assets"

Write-Host "==> Run tests" -ForegroundColor Cyan
& $VenvPython -m unittest discover -s tests -v
Assert-LastExitCode "Run tests"

Write-Host "==> Build Windows application" -ForegroundColor Cyan
& $VenvPython -m PyInstaller --clean --noconfirm (Join-Path $Root "packaging\autohome_exporter.spec")
Assert-LastExitCode "Build Windows application"

$Candidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 5\ISCC.exe"
)
$Iscc = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Iscc) {
    throw "Inno Setup 6 was not found. Install it from https://jrsoftware.org/isinfo.php"
}

Write-Host "==> Build installer" -ForegroundColor Cyan
& $Iscc (Join-Path $Root "packaging\installer.iss")
Assert-LastExitCode "Build installer"

Write-Host "==> Build portable ZIP" -ForegroundColor Cyan
$ZipPath = Join-Path $Root "dist\AutohomeSpecExporter_Portable_v1.0.4.zip"
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Compress-Archive -Path (Join-Path $Root "dist\AutohomeSpecExporter\*") -DestinationPath $ZipPath

Write-Host ""
Write-Host "Build completed:" -ForegroundColor Green
Write-Host "  App folder: $Root\dist\AutohomeSpecExporter"
Write-Host "  Installer: $Root\dist\AutohomeSpecExporter_Setup_v1.0.4.exe"
Write-Host "  Portable ZIP: $ZipPath"
