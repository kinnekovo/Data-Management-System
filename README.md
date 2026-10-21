# 基于 MongoDB 的问卷系统

《当代数据管理系统》课程大作业一的第一阶段完整实现。系统提供账号注册登录、问卷和题目管理、四种底层题型、条件跳转、登录后填写、匿名与重复提交策略，以及基于 MongoDB 聚合的实时统计。默认采用 Windows 本地原生部署，Docker 仅保留为可选方案。

## 技术栈与环境

| 组件 | 要求 | 本次验证环境 |
|---|---|---|
| Windows / PowerShell | Windows 10/11，PowerShell 5.1+ | Windows，PowerShell 5.1 |
| Python | 3.11+ | 3.13.9 |
| Node.js | 22.12+ | 24.19.0 |
| npm | 随 Node.js 安装 | 11.17.0 |
| MongoDB Community Server | 7.x 或 8.x | 8.3.1 |
| mongosh | 建议安装并加入 PATH | 2.12.0 |

后端为 FastAPI + PyMongo，密码使用 Argon2 哈希，身份令牌使用 JWT；前端为 Vue 3 + Vue Router + Vite。数据库默认 URI 是 `mongodb://127.0.0.1:27017`，默认数据库是 `survey_system`。

## 一键启动（推荐）

在项目根目录执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-all.ps1
```

脚本会：

1. 缺少 `.env` 时从 `.env.example` 创建，不覆盖已有配置；
2. 检查 Python、Node.js、npm、MongoDB 和端口；
3. 默认 MongoDB 未运行且本机能找到 `mongod.exe` 时，在 `.local-mongodb-data` 启动项目专用实例；
4. 首次运行时创建 `backend\.venv` 并安装后端依赖，安装前端依赖；
5. 分别打开后端和前端 PowerShell 窗口，等待真实就绪检查通过；
6. 打开 `http://127.0.0.1:5173`。

不自动打开浏览器：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-all.ps1 -NoBrowser
```

脚本不会注册 Windows 服务、修改系统执行策略、终止占用端口的进程，也不会清理任何 MongoDB 数据。关闭服务时在后端和前端窗口按 `Ctrl+C`；项目专用 MongoDB 可在任务管理器中通过命令行参数中的 `.local-mongodb-data` 识别。

## 分步启动

### 1. 准备 MongoDB

从 [MongoDB Community Server](https://www.mongodb.com/try/download/community) 安装服务器。服务名称因安装方式而异，先查询：

```powershell
Get-Service | Where-Object {
    $_.Name -match 'mongo' -or $_.DisplayName -match 'mongo'
} | Format-Table Name, DisplayName, Status, StartType
```

通过 Windows“服务”启动查到的服务，或按实际配置文件启动 `mongod`。验证真实连接：

```powershell
mongosh "mongodb://127.0.0.1:27017/admin" --quiet --eval `
  "JSON.stringify(db.runCommand({ping:1}))"
```

结果应包含 `"ok":1`。如果使用认证或其他端口，复制配置并编辑：

```powershell
Copy-Item .env.example .env
notepad .env
```

`MONGODB_URI` 和 `MONGODB_DATABASE` 均可修改。密码含 `@`、`:`、`/` 等字符时需 URL 编码；不要提交含真实凭据的 `.env`。

### 2. 启动 FastAPI

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

无需激活虚拟环境的脚本方式：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
```

### 3. 启动 Vue

另开一个根目录 PowerShell：

```powershell
Set-Location frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

或执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1
```

Vite 将 `/api` 代理到 `.env` 中的 `VITE_API_PROXY_TARGET`，组件不硬编码后端地址。

## 环境检查与功能验收

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-env.ps1
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/live
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ready
```

`live` 只说明后端进程存活；`ready` 会执行真实 MongoDB `ping`，连接失败时返回 503。浏览器检查地址：

- 前端：`http://127.0.0.1:5173`
- Swagger：`http://127.0.0.1:8000/docs`
- OpenAPI：`http://127.0.0.1:8000/openapi.json`

建议验收流程：注册创建者账号 → 新建问卷 → 添加单选、多选、文本、数字题 → 为前置题配置向后跳转 → 发布并复制链接 → 用另一账号填写 → 返回创建者账号查看实时统计。匿名问卷的管理端响应列表不会返回填写者标识；禁止重复时由 MongoDB 唯一索引处理并发提交。

## 测试

测试使用名称带随机后缀且以 `_test` 结尾的独立数据库，结束后只删除该次测试创建的数据库：

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest -q
Set-Location ..\frontend
npm run build
```

演示数据必须写入以 `_demo` 结尾的独立数据库：

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m app.db.seed_demo --database survey_system_stage1_demo
```

脚本会输出演示账号、密码和问卷 slug；它只替换带 `stage1_demo_v1` 标记的数据，拒绝写入名称不以 `_demo` 结尾的数据库。

## 常见问题

- **MongoDB 无法连接**：先运行 `mongosh ... ping`，再核对 `.env` 的 URI、端口、认证库和 URL 编码。查看实际 Windows 服务名，不要假定名称固定。
- **27017 冲突**：用 `Get-NetTCPConnection -LocalPort 27017 -State Listen` 查进程；确认是否为预期 MongoDB。项目脚本不会强制结束它。
- **8000 或 5173 冲突**：环境脚本会识别本项目健康接口和 Vite 页面；其他程序占用时先自行关闭，或分步启动时显式改端口并同步代理配置。
- **虚拟环境无法激活**：直接用 `backend\.venv\Scripts\python.exe`，无需更改执行策略。
- **PowerShell 禁止脚本**：命令中的 `-ExecutionPolicy Bypass` 仅影响该子进程；无需修改系统级策略。
- **npm install 失败**：检查网络、代理与 npm registry，再重试；不要删除锁文件来掩盖版本问题。
- **ready 返回 503**：后端已启动但 MongoDB 未就绪；查看响应中的明确错误详情及 MongoDB 日志。

## 文档

- [系统设计](docs/system-design.md)
- [数据库设计](docs/database-design.md)
- [API 文档](docs/api.md)
- [测试与结果](docs/testing.md)
- [最终报告](docs/final-report.md)
- [AI 使用日志](docs/ai-usage-log.md)
- [本地部署细节](docs/local-deployment.md)

可选的 `docker-compose.yml` 和 Dockerfile 仅用于补充部署；本地启动、开发与验收都不依赖 Docker。
