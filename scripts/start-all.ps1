[CmdletBinding()]
param(
    [ValidateRange(30, 900)]
    [int]$StartupTimeoutSeconds = 300,

    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$EnvPath = Join-Path $ProjectRoot ".env"
$ExampleEnvPath = Join-Path $ProjectRoot ".env.example"
$CheckScript = Join-Path $PSScriptRoot "check-env.ps1"
$BackendScript = Join-Path $PSScriptRoot "start-backend.ps1"
$FrontendScript = Join-Path $PSScriptRoot "start-frontend.ps1"
$PowerShellExe = (Get-Command powershell.exe -ErrorAction Stop).Source
$MongoDataDir = Join-Path $ProjectRoot ".local-mongodb-data"
$MongoLogDir = Join-Path $ProjectRoot ".local-mongodb-logs"
$MongoLogPath = Join-Path $MongoLogDir "mongod.log"

function Get-DotEnvValue {
    param([string]$Name)
    if (-not (Test-Path -LiteralPath $EnvPath)) { return $null }
    $pattern = "^\s*$([regex]::Escape($Name))\s*="
    $line = Get-Content -LiteralPath $EnvPath |
        Where-Object { $_ -match $pattern } |
        Select-Object -Last 1
    if (-not $line) { return $null }
    return (($line -split "=", 2)[1].Trim()).Trim('"').Trim("'")
}

function Test-TcpPort {
    param([int]$Port)
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $task = $client.ConnectAsync("127.0.0.1", $Port)
        return $task.Wait(500) -and $client.Connected
    }
    catch { return $false }
    finally { $client.Dispose() }
}

function Test-MongoReady {
    param([string]$Uri)
    $mongosh = Get-Command mongosh.exe -ErrorAction SilentlyContinue
    if (-not $mongosh) { return $false }
    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $mongosh.Source $Uri --quiet --eval "quit(db.runCommand({ ping: 1 }).ok ? 0 : 2)" *> $null
        return $LASTEXITCODE -eq 0
    }
    finally {
        $ErrorActionPreference = $previousErrorAction
    }
}

function Test-BackendReady {
    try {
        $response = Invoke-RestMethod `
            -Uri "http://127.0.0.1:8000/api/v1/health/ready" `
            -TimeoutSec 2
        return $response.status -eq "ready" -and $response.database -eq "connected"
    }
    catch { return $false }
}

function Test-FrontendReady {
    try {
        $response = Invoke-WebRequest `
            -UseBasicParsing `
            -Uri "http://127.0.0.1:5173" `
            -TimeoutSec 2
        return (
            $response.StatusCode -eq 200 -and
            $response.Content -match 'id="app"' -and
            $response.Content -match '/src/main.js'
        )
    }
    catch { return $false }
}

function Wait-ForService {
    param(
        [string]$Name,
        [scriptblock]$Probe,
        [System.Diagnostics.Process]$Process
    )

    $deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
    $nextMessage = Get-Date
    while ((Get-Date) -lt $deadline) {
        if (& $Probe) {
            Write-Host "[OK] $Name 已就绪。" -ForegroundColor Green
            return
        }
        if ($Process -and $Process.HasExited) {
            throw "$Name 启动进程已退出，退出码：$($Process.ExitCode)。请查看对应 PowerShell 窗口中的日志。"
        }
        if ((Get-Date) -ge $nextMessage) {
            Write-Host "正在等待 $Name……"
            $nextMessage = (Get-Date).AddSeconds(10)
        }
        Start-Sleep -Seconds 1
    }
    throw "等待 $Name 超过 $StartupTimeoutSeconds 秒。请查看对应 PowerShell 窗口中的日志。"
}

function Start-ProjectWindow {
    param(
        [string]$Title,
        [string]$ScriptPath
    )

    Write-Host "正在启动 $Title……" -ForegroundColor Cyan
    return Start-Process `
        -FilePath $PowerShellExe `
        -ArgumentList @(
            "-NoExit",
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", "`"$ScriptPath`""
        ) `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Normal `
        -PassThru
}

Write-Host "第一阶段问卷系统一键启动" -ForegroundColor Cyan
Write-Host "项目目录：$ProjectRoot"

if (-not (Test-Path -LiteralPath $EnvPath)) {
    if (-not (Test-Path -LiteralPath $ExampleEnvPath)) {
        throw "未找到 .env 或 .env.example，无法准备本地配置。"
    }
    Copy-Item -LiteralPath $ExampleEnvPath -Destination $EnvPath
    Write-Host "[OK] 已从 .env.example 创建 .env。" -ForegroundColor Green
}

$mongoUri = Get-DotEnvValue "MONGODB_URI"
if (-not $mongoUri) { $mongoUri = "mongodb://127.0.0.1:27017" }
$mongoPort = 27017
if ($mongoUri -match '^mongodb://(?:[^@/]+@)?(?:\[[^\]]+\]|[^:/,]+):(\d+)') {
    $mongoPort = [int]$Matches[1]
}

$mongoProcess = $null
if (-not (Test-MongoReady -Uri $mongoUri)) {
    $isDefaultLocalMongo = $mongoUri -match '^mongodb://(127\.0\.0\.1|localhost):27017/?$'
    if ($isDefaultLocalMongo -and -not (Test-TcpPort -Port $mongoPort)) {
        $mongod = Get-Command mongod.exe -ErrorAction SilentlyContinue
        if ($mongod) {
            New-Item -ItemType Directory -Force -Path $MongoDataDir, $MongoLogDir | Out-Null
            Write-Host "正在启动项目专用 MongoDB：$mongoUri" -ForegroundColor Cyan
            $mongoProcess = Start-Process `
                -FilePath $mongod.Source `
                -ArgumentList @(
                    "--dbpath", "`"$MongoDataDir`"",
                    "--logpath", "`"$MongoLogPath`"",
                    "--logappend",
                    "--bind_ip", "127.0.0.1",
                    "--port", "$mongoPort"
                ) `
                -WorkingDirectory $ProjectRoot `
                -WindowStyle Normal `
                -PassThru
            Wait-ForService `
                -Name "MongoDB" `
                -Probe { Test-MongoReady -Uri $mongoUri } `
                -Process $mongoProcess
        }
    }
}

Write-Host "正在检查 Python、Node.js、npm、MongoDB 和端口……"
& $CheckScript
if ($LASTEXITCODE -ne 0) {
    throw "环境检查未通过。请按上方提示检查 MongoDB 配置或处理端口冲突，然后重新运行本脚本。"
}

$backendProcess = $null
if (Test-BackendReady) {
    Write-Host "[OK] FastAPI 已在 http://127.0.0.1:8000 运行。" -ForegroundColor Green
}
else {
    $backendProcess = Start-ProjectWindow -Title "FastAPI 后端" -ScriptPath $BackendScript
    Wait-ForService -Name "FastAPI 与 MongoDB" -Probe ${function:Test-BackendReady} -Process $backendProcess
}

$frontendProcess = $null
if (Test-FrontendReady) {
    Write-Host "[OK] Vue 前端已在 http://127.0.0.1:5173 运行。" -ForegroundColor Green
}
else {
    $frontendProcess = Start-ProjectWindow -Title "Vue 前端" -ScriptPath $FrontendScript
    Wait-ForService -Name "Vue 前端" -Probe ${function:Test-FrontendReady} -Process $frontendProcess
}

Write-Host ""
Write-Host "第一阶段本地环境已启动：" -ForegroundColor Green
Write-Host "  前端：  http://127.0.0.1:5173"
Write-Host "  API：   http://127.0.0.1:8000"
Write-Host "  Swagger：http://127.0.0.1:8000/docs"
Write-Host "  Ready： http://127.0.0.1:8000/api/v1/health/ready"
if ($mongoProcess) {
    Write-Host "  MongoDB 日志：$MongoLogPath"
}
Write-Host "关闭服务时，请在新打开的服务窗口中按 Ctrl+C；MongoDB 也可在任务管理器中按本项目数据目录识别。"

if (-not $NoBrowser) {
    Start-Process "http://127.0.0.1:5173"
}
