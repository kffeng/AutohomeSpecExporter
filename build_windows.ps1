$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "==> 检查 Python" -ForegroundColor Cyan
$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
    throw "未找到 Python。请安装 Python 3.11 64 位，并勾选 Add Python to PATH。"
}

$Venv = Join-Path $Root ".build-venv"
if (-not (Test-Path $Venv)) {
    python -m venv $Venv
}
$VenvPython = Join-Path $Venv "Scripts\python.exe"

Write-Host "==> 安装构建依赖" -ForegroundColor Cyan
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r (Join-Path $Root "requirements-build.txt")

Write-Host "==> 运行测试" -ForegroundColor Cyan
& $VenvPython -m unittest discover -s tests -v

Write-Host "==> 打包 Windows 程序" -ForegroundColor Cyan
& $VenvPython -m PyInstaller --clean --noconfirm (Join-Path $Root "packaging\autohome_exporter.spec")

$Candidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 5\ISCC.exe"
)
$Iscc = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Iscc) {
    throw "未找到 Inno Setup。请安装 Inno Setup 6：https://jrsoftware.org/isinfo.php"
}

Write-Host "==> 生成安装包" -ForegroundColor Cyan
& $Iscc (Join-Path $Root "packaging\installer.iss")

Write-Host "==> 生成便携版 ZIP" -ForegroundColor Cyan
$ZipPath = Join-Path $Root "dist\AutohomeSpecExporter_Portable_v1.0.0.zip"
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Compress-Archive -Path (Join-Path $Root "dist\AutohomeSpecExporter\*") -DestinationPath $ZipPath

Write-Host ""
Write-Host "构建完成：" -ForegroundColor Green
Write-Host "  程序目录: $Root\dist\AutohomeSpecExporter"
Write-Host "  安装包:   $Root\dist\AutohomeSpecExporter_Setup_v1.0.0.exe"
Write-Host "  便携包:   $ZipPath"
