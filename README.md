# 基于 MongoDB 的问卷系统

这是《当代数据管理系统》课程大作业一的阶段一工程。当前完成 **M1 基础环境**：Vue 3 + Vite 前端、FastAPI + PyMongo 后端、本地 MongoDB 连接、健康检查、幂等索引初始化、安全 smoke check 和基础测试。

默认部署方式是 **Windows 本地原生运行**，不需要 Docker。注册登录、问卷 CRUD、题目、提交、统计、校验和条件跳转属于 M2～M5，尚未实现。

## 1. 环境要求

| 软件 | 兼容范围 | 本次验证环境 |
|---|---|---|
| Windows | Windows 10/11 + PowerShell 5.1 或更高 | Windows + PowerShell |
| Python | 3.11 或更高 | Python 3.12.14 完成后端测试 |
| Node.js | 22.12 或更高 | Node.js 24.19.0 |
| npm | 随受支持的 Node.js 安装 | npm 11.17.0 |
| MongoDB Community Server | 7.x 或 8.x | 本机检测到 MongoDB 8.3.1 |
| mongosh | 建议安装并加入 PATH | 本机检测到 mongosh 2.12.0 |

项目默认连接 `mongodb://127.0.0.1:27017`，数据库名为 `survey_system`。测试写入仅允许使用名称以 `_test` 结尾的 `survey_system_test`。

## 2. 第一次运行

从项目根目录打开 PowerShell：

```powershell
Copy-Item .env.example .env
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-env.ps1
```

`-ExecutionPolicy Bypass` 只作用于这一次新进程，不修改系统级执行策略。如果检查报告 MongoDB 未连接，请先完成下一节。

## 3. 安装和启动本地 MongoDB

从 [MongoDB Community Server 官方下载页](https://www.mongodb.com/try/download/community) 下载 Windows MSI。安装向导中可以选择把 MongoDB 注册为 Windows 服务；也可以按 [MongoDB 官方 Windows 运行说明](https://www.mongodb.com/docs/manual/administration/run-mongodb-windows/) 手工启动 `mongod`。

不要假定服务名一定是 `MongoDB`。先查找实际名称和状态：

```powershell
Get-Service | Where-Object {
    $_.Name -match 'mongo' -or $_.DisplayName -match 'mongo'
} | Format-Table Name, DisplayName, Status, StartType
```

若安装器已注册服务，请通过 Windows“服务”界面启动查到的服务，或在管理员 PowerShell 中按实际服务名执行 `Start-Service`。如果使用 ZIP/手工安装，请按自己的配置文件指定 `dbPath` 和日志目录启动 `mongod`；项目脚本不会替你注册服务、修改系统配置或终止进程。

确认本地连接：

```powershell
mongosh "mongodb://127.0.0.1:27017/admin" --quiet --eval `
  "JSON.stringify(db.runCommand({ping:1}))"
```

应看到包含 `"ok":1` 的结果。若本机启用了 MongoDB 认证，请把 `.env` 中的 URI 改成实际连接串，例如：

```dotenv
MONGODB_URI=mongodb://username:password@127.0.0.1:27017/survey_system?authSource=admin
```

用户名或密码含 `@`、`:`、`/` 等字符时必须进行 URL 编码。不要提交包含真实密码的 `.env`。

## 4. 启动后端

题目要求的标准 PowerShell 流程如下：

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

也可以从项目根目录使用启动脚本。脚本会创建 `backend\.venv`（如不存在）、检查依赖、必要时安装 `requirements.txt`，并始终使用虚拟环境中的 Python：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
```

后端入口是 `app.main:app`。配置会从项目根目录 `.env` 读取，与当前 PowerShell 工作目录无关。启动时会创建或核对索引，重复启动不会删除数据。

## 5. 启动前端

另开一个 PowerShell，从项目根目录执行：

```powershell
Set-Location frontend
npm install
npm run dev
```

或使用脚本：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1
```

前端默认位于 `http://localhost:5173`。浏览器请求相对路径 `/api`，Vite 在 [vite.config.js](frontend/vite.config.js) 中统一代理到 `http://127.0.0.1:8000`；Vue 组件没有硬编码后端主机地址。需要变更目标时可在启动前设置 `VITE_API_PROXY_TARGET`。

## 6. 功能验收

启动 MongoDB、后端和前端后执行：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/live
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ready

Set-Location backend
.\.venv\Scripts\python.exe -m app.db.smoke_check
.\.venv\Scripts\python.exe -m pytest

Set-Location ..\frontend
npm run build
```

预期结果：

- `/live` 返回 `status = alive`，只证明 FastAPI 进程存活。
- `/ready` 返回 `status = ready` 和 `database = connected`，证明真实 MongoDB `ping` 成功。
- smoke check 输出 `status = passed`、`indexes_verified = 5`；它只在测试数据库插入一个带随机标识的临时记录，并在结束时清理。
- 打开 `http://localhost:5173` 后显示“后端与 MongoDB 已就绪”。MongoDB 未运行时页面仍能打开，并显示明确错误。
- Swagger 位于 `http://127.0.0.1:8000/docs`。

## 7. 常见问题

### MongoDB 无法连接

运行 `scripts/check-env.ps1`，再用 `mongosh` 执行 ping。检查 MongoDB 进程或实际 Windows 服务状态、`.env` 的 `MONGODB_URI`、认证参数和日志。应用不会自动启动或清空 MongoDB。

### 27017 端口冲突

先确定监听程序：

```powershell
Get-NetTCPConnection -State Listen -LocalPort 27017 |
    Select-Object LocalAddress, LocalPort, OwningProcess
```

如果该端口上的 MongoDB 能通过 ping，它就是预期服务；否则请修改 MongoDB 配置与 `.env` URI，或自行处理占用程序。项目脚本不会强制终止任何进程。

### 8000 或 5173 端口冲突

`check-env.ps1` 会请求健康接口或页面标题，区分本项目服务和未知占用。可用脚本参数改端口：

```powershell
.\scripts\start-backend.ps1 -Port 8010
$env:VITE_API_PROXY_TARGET = "http://127.0.0.1:8010"
.\scripts\start-frontend.ps1 -Port 5180
```

### 虚拟环境无法激活

启动脚本不依赖激活，直接调用 `backend\.venv\Scripts\python.exe`。也可以这样安装：

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
```

### npm 安装失败

确认 `node --version` 和 `npm --version`，检查网络或 npm registry 配置，然后在 `frontend` 中重试 `npm install`。不要删除 lockfile；助教可使用 `npm ci` 得到完全锁定的依赖。

### PowerShell 阻止脚本执行

使用本文的 `powershell -NoProfile -ExecutionPolicy Bypass -File ...` 形式，仅对单次子进程放行脚本。无需修改机器级执行策略，也不应关闭安全软件。

## 8. 可选 Docker 方式

`Dockerfile` 和 `docker-compose.yml` 仅为可选兼容方案，本地原生运行不依赖它们。Compose 内部仍使用服务名 `mongo:27017`，并把容器 MongoDB 映射到宿主机 `127.0.0.1:27018`，避免与默认本地 MongoDB `27017` 冲突。

```powershell
docker compose up -d --build
```

不要对既有环境运行 `docker compose down -v`，因为它会删除 Compose 管理的 MongoDB Volume。本地 MongoDB 数据不依赖 Docker Volume。

## 9. M1 边界

本次只调整部署与基础设施。数据集合、索引名称、健康接口和前端连通性页面保持不变。下一阶段 M2 才会开发账户、权限和问卷草稿功能。

详细资料：[系统设计](docs/system-design.md)、[本地部署说明](docs/local-deployment.md)、[数据库设计](docs/database-design.md)、[API](docs/api.md)、[测试记录](docs/tests.md)、[AI 使用记录](docs/ai-usage-log.md)。
