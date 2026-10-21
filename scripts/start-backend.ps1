[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $ProjectRoot "backend"
$RequirementsPath = Join-Path $BackendDir "requirements.txt"
$VenvDir = Join-Path $BackendDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

$systemPython = Get-Command python.exe -ErrorAction SilentlyContinue
if (-not $systemPython) {
    throw "未找到 Python。请安装 Python 3.11 或更高版本并加入 PATH。"
}

if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host "未找到 backend\.venv，正在创建虚拟环境……" -ForegroundColor Yellow
    $ErrorActionPreference = "Continue"
    & $systemPython.Source -m venv $VenvDir
    $venvExitCode = $LASTEXITCODE
    $ErrorActionPreference = "Stop"
    if ($venvExitCode -ne 0 -or -not (Test-Path -LiteralPath $VenvPython)) {
        throw "虚拟环境创建失败。请检查 Python 安装，然后在 backend 目录执行 python -m venv .venv。"
    }
}

$ErrorActionPreference = "Continue"
& $VenvPython -c "import fastapi, jwt, pwdlib, pydantic_settings, pymongo, uvicorn" *> $null
$dependencyCheckExitCode = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($dependencyCheckExitCode -ne 0) {
    Write-Host "后端依赖尚未完整安装，正在从 requirements.txt 安装……" -ForegroundColor Yellow
    $ErrorActionPreference = "Continue"
    & $VenvPython -m pip install -r $RequirementsPath
    $pipExitCode = $LASTEXITCODE
    $ErrorActionPreference = "Stop"
    if ($pipExitCode -ne 0) {
        throw "后端依赖安装失败。请检查网络和 pip 配置后重试。"
    }
}

Write-Host "启动 FastAPI：http://127.0.0.1:$Port" -ForegroundColor Green
Write-Host "Swagger：http://127.0.0.1:$Port/docs"
Push-Location $BackendDir
try {
    $ErrorActionPreference = "Continue"
    & $VenvPython -m uvicorn app.main:app --reload --host 127.0.0.1 --port $Port
    $uvicornExitCode = $LASTEXITCODE
    $ErrorActionPreference = "Stop"
    if ($uvicornExitCode -ne 0) { throw "Uvicorn 启动失败，退出码：$uvicornExitCode" }
}
finally {
    Pop-Location
}
