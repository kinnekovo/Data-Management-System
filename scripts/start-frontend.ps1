[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 5173
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$FrontendDir = Join-Path $ProjectRoot "frontend"
$PackageJson = Join-Path $FrontendDir "package.json"
$ViteCommand = Join-Path $FrontendDir "node_modules\.bin\vite.cmd"
$EnvPath = Join-Path $ProjectRoot ".env"

$node = Get-Command node.exe -ErrorAction SilentlyContinue
$npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $node -or -not $npm) {
    throw "未找到 Node.js 或 npm.cmd。请安装 Node.js 22.12 或更高版本并加入 PATH。"
}
if (-not (Test-Path -LiteralPath $PackageJson)) {
    throw "未找到 frontend\package.json。"
}

if (-not $env:VITE_API_PROXY_TARGET -and (Test-Path -LiteralPath $EnvPath)) {
    $proxyLine = Get-Content -LiteralPath $EnvPath |
        Where-Object { $_ -match '^\s*VITE_API_PROXY_TARGET\s*=' } |
        Select-Object -Last 1
    if ($proxyLine) {
        $env:VITE_API_PROXY_TARGET = (($proxyLine -split '=', 2)[1].Trim()).Trim('"').Trim("'")
    }
}

Push-Location $FrontendDir
try {
    if (-not (Test-Path -LiteralPath $ViteCommand)) {
        Write-Host "前端依赖尚未安装，正在执行 npm install……" -ForegroundColor Yellow
        $ErrorActionPreference = "Continue"
        & $npm.Source install
        $npmInstallExitCode = $LASTEXITCODE
        $ErrorActionPreference = "Stop"
        if ($npmInstallExitCode -ne 0) { throw "npm install 失败，请检查网络和 npm 配置。" }
    }

    Write-Host "启动 Vue：http://127.0.0.1:$Port" -ForegroundColor Green
    $ErrorActionPreference = "Continue"
    & $npm.Source run dev -- --host 127.0.0.1 --port $Port
    $viteExitCode = $LASTEXITCODE
    $ErrorActionPreference = "Stop"
    if ($viteExitCode -ne 0) { throw "Vite 启动失败，退出码：$viteExitCode" }
}
finally {
    Pop-Location
}
