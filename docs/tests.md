# M1 测试记录

执行日期：2026-10-19（Asia/Shanghai）。以下结果均来自当前工作区的真实命令；没有把 Mock 结果记作真实 MongoDB 连接。

## 本地原生部署调整后的验证

测试环境：Windows、Python 3.13.9、Node.js 24.19.0、npm 11.17.0、MongoDB Server 8.3.1、mongosh 2.12.0。MongoDB 由本机 `mongod.exe` 使用隔离目录 `.local-mongodb-data` 监听 `127.0.0.1:27017`，没有使用 Docker 容器或 Docker Volume。

| 检查 | 实际命令或方式 | 结果 | 真实结果 |
|---|---|---|---|
| 环境检查的未启动提示 | `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-env.ps1`（服务启动前） | PASS | 正确报告 MongoDB 未监听，8000、5173 可用；退出码 1 |
| 后端虚拟环境与依赖 | `.\scripts\start-backend.ps1` | PASS | 自动创建 `backend\.venv`，从 `requirements.txt` 安装成功，并使用该环境启动 Uvicorn |
| 后端本地启动 | `.\scripts\start-backend.ps1` | PASS | `app.main:app` 启动完成；日志显示 `MongoDB indexes are ready` |
| 前端本地启动 | `.\scripts\start-frontend.ps1` | PASS | Vite 8.3.4 在 `127.0.0.1:5173` 启动，ready in 876 ms |
| 环境检查的运行中识别 | `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-env.ps1` | PASS | MongoDB ping 成功；8000 识别为本项目 FastAPI；5173 识别为本项目前端 |
| 后端存活检查 | `Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/live` | PASS | HTTP 200；`status=alive`，`service=survey-system-api` |
| 真实 MongoDB 就绪检查 | `Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ready` | PASS | HTTP 200；`status=ready`，`database=connected`；路由执行真实 `ping` |
| MongoDB smoke check | `..\.venv\Scripts\python.exe -m app.db.smoke_check`（在 `backend`） | PASS | 使用 `survey_system_test`；验证 5 个索引；临时文档写入、读取、按 token 清理成功 |
| 开发库索引核对 | `mongosh ... --eval 'db.getCollectionNames()...'` | PASS | `users`: `_id_`, `ux_users_username`；`surveys`: `_id_`, `ux_surveys_slug`, `ix_surveys_owner_created`；`responses`: `_id_`, `ix_responses_survey_submitted`, `ux_responses_submission_guard` |
| 后端测试 | `.\.venv\Scripts\python.exe -m pytest -q`（在 `backend`） | PASS | 8 passed in 0.95s；包含配置默认值、路由、ready 成功/失败和索引定义 |
| 前端生产构建 | `npm run build`（在 `frontend`） | PASS | Vite 8.3.4；12 modules transformed；built in 182 ms |
| 前端 HTTP | `Invoke-WebRequest http://127.0.0.1:5173` | PASS | HTTP 200，返回 Vite 页面 |
| 浏览器三端联调 | 浏览器打开 `http://127.0.0.1:5173` | PASS | 页面实际显示“后端与 MongoDB 已就绪”，由 `/api/v1/health/ready` 的真实响应驱动 |
| 不启动 Docker 运行 | `docker compose ... ps -a` 并核对监听进程 | PASS | Compose 项目无容器；27017 为本机 `mongod`，8000 为本机 Python，5173 为本机 Node |
| 可选 Compose 静态解析 | `docker compose --env-file .env.example config --quiet` | PASS | 退出码 0；可选部署配置仍可解析 |
| Windows 服务开机启动 | 未注册或修改系统服务 | NOT RUN | 当前验证使用隔离的手动 `mongod`；未擅自修改 Windows 服务配置 |
| 可选 Docker 三服务运行 | 未重新拉取或启动容器 | NOT RUN | Docker 已降为可选方式，本次验收目标由本地原生链路完成 |

本次没有最终失败项。开发过程中曾发现 Windows PowerShell 5.1 对无 BOM 中文脚本解析异常，以及原生命令 stderr 在 `$ErrorActionPreference = 'Stop'` 下会中断脚本；三个脚本已保存为 UTF-8 BOM，并针对原生命令按退出码判断，修复后已复跑通过。

## 数据安全

- 没有清空开发数据库，没有删除 MongoDB 数据目录或 Docker Volume。
- smoke check 只访问 `survey_system_test`，并且只删除本次生成且带随机 token 的临时记录。
- 本次手动 MongoDB 使用工作区内已忽略的 `.local-mongodb-data`，与其他项目的数据目录隔离。
- `.env` 未自动创建或覆盖；测试使用代码中的本地默认值。
