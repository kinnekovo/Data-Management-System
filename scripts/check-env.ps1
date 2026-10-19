[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$EnvPath = Join-Path $ProjectRoot ".env"
$ExampleEnvPath = Join-Path $ProjectRoot ".env.example"
$hasError = $false

function Write-CheckResult {
    param(
        [string]$Level,
        [string]$Message
    )
    $color = switch ($Level) {
        "OK" { "Green" }
        "WARN" { "Yellow" }
        default { "Red" }
    }
    Write-Host "[$Level] $Message" -ForegroundColor $color
}

function Get-DotEnvValue {
    param([string]$Name)
    if (-not (Test-Path -LiteralPath $EnvPath)) { return $null }
    $pattern = "^\s*$([regex]::Escape($Name))\s*="
    $line = Get-Content -LiteralPath $EnvPath | Where-Object { $_ -match $pattern } | Select-Object -Last 1
    if (-not $line) { return $null }
    $value = ($line -split "=", 2)[1].Trim()
    return $value.Trim('"').Trim("'")
}

function Test-TcpPort {
    param([int]$Port)
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $task = $client.ConnectAsync("127.0.0.1", $Port)
        if (-not $task.Wait(500)) { return $false }
        return $client.Connected
    }
    catch { return $false }
    finally { $client.Dispose() }
}

Write-Host "M1 本地环境检查" -ForegroundColor Cyan
Write-Host "项目目录：$ProjectRoot"

$python = Get-Command python.exe -ErrorAction SilentlyContinue
if ($python) {
    $pythonVersion = & $python.Source --version 2>&1
    Write-CheckResult "OK" "Python：$pythonVersion ($($python.Source))"
}
else {
    Write-CheckResult "ERROR" "未找到 Python。请安装 Python 3.11 或更高版本并加入 PATH。"
    $hasError = $true
}

$node = Get-Command node.exe -ErrorAction SilentlyContinue
if ($node) {
    Write-CheckResult "OK" "Node.js：$(& $node.Source --version) ($($node.Source))"
}
else {
    Write-CheckResult "ERROR" "未找到 Node.js。请安装 Node.js 22.12 或更高版本。"
    $hasError = $true
}

$npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if ($npm) {
    Write-CheckResult "OK" "npm：$(& $npm.Source --version) ($($npm.Source))"
}
else {
    Write-CheckResult "ERROR" "未找到 npm.cmd。请检查 Node.js 安装。"
    $hasError = $true
}

if (Test-Path -LiteralPath $EnvPath) {
    Write-CheckResult "OK" "已找到 .env。"
}
elseif (Test-Path -LiteralPath $ExampleEnvPath) {
    Write-CheckResult "WARN" "未找到 .env；应用可使用本地默认值。建议执行：Copy-Item .env.example .env"
}
else {
    Write-CheckResult "ERROR" "缺少 .env.example。"
    $hasError = $true
}

$mongoUri = Get-DotEnvValue "MONGODB_URI"
if (-not $mongoUri) { $mongoUri = "mongodb://127.0.0.1:27017" }
$mongoPort = 27017
if ($mongoUri -match '^mongodb://(?:[^@/]+@)?(?:\[[^\]]+\]|[^:/,]+):(\d+)') {
    $mongoPort = [int]$Matches[1]
}
$mongoReady = $false
$mongoPortListening = Test-TcpPort $mongoPort
$mongosh = Get-Command mongosh.exe -ErrorAction SilentlyContinue
if ($mongosh) {
    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $mongosh.Source $mongoUri --quiet --eval "quit(db.runCommand({ ping: 1 }).ok ? 0 : 2)" *> $null
        $mongoExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorAction
    }
    if ($mongoExitCode -eq 0) {
        $mongoReady = $true
        Write-CheckResult "OK" "MongoDB ping 成功：$mongoUri"
    }
    else {
        if ($mongoPortListening) {
            Write-CheckResult "ERROR" "端口 $mongoPort 已被占用，但 mongosh ping 失败；请核对它是否为预期 MongoDB 以及认证参数。"
        }
        else {
            Write-CheckResult "ERROR" "端口 $mongoPort 未监听，MongoDB 尚未运行：$mongoUri"
        }
        $hasError = $true
    }
}
else {
    Write-CheckResult "WARN" "未找到 mongosh，无法执行真实 MongoDB ping。"
    if (-not $mongoPortListening) { $hasError = $true }
}

if (-not $mongoReady) {
    Write-Host "  请在 Windows 服务中查找实际的 MongoDB 服务名称并启动，或用安装目录中的 mongod 配置文件启动。"
    Write-Host "  可用 Get-Service | Where-Object { `$_.Name -match 'mongo' -or `$_.DisplayName -match 'mongo' } 查找。"
}

foreach ($port in 8000, 5173) {
    if (-not (Test-TcpPort $port)) {
        Write-CheckResult "OK" "端口 $port 当前空闲。"
        continue
    }

    if ($port -eq 8000) {
        try {
            $result = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health/live" -TimeoutSec 2
            if ($result.status -eq "alive") {
                Write-CheckResult "OK" "端口 8000 正由本项目 FastAPI 使用。"
                continue
            }
        }
        catch {}
    }
    elseif ($port -eq 5173) {
        try {
            $result = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:5173" -TimeoutSec 2
            if (
                $result.StatusCode -eq 200 -and
                $result.Content -match 'id="app"' -and
                $result.Content -match '/src/main.js'
            ) {
                Write-CheckResult "OK" "端口 5173 正由本项目前端使用。"
                continue
            }
        }
        catch {}
    }

    Write-CheckResult "ERROR" "端口 $port 已被其他或无法识别的程序占用；脚本不会终止该程序。"
    $hasError = $true
}

if ($hasError) {
    Write-Host "环境检查发现需要处理的问题。" -ForegroundColor Red
    exit 1
}

Write-Host "环境检查通过。" -ForegroundColor Green
