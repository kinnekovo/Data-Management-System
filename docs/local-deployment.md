# 第一阶段 Windows 本地原生部署说明

本文记录从 Docker 默认部署迁移到本地原生部署的基础设施调整。完整业务功能和验收入口见根目录 `README.md`。

## 调整背景

原始 M1 以 Docker Compose 同时运行 MongoDB、FastAPI 和 Vite。为降低课程助教验收门槛，默认流程现改为 Windows 本地原生部署：MongoDB Community Server 监听 `127.0.0.1:27017`，FastAPI 使用 `backend\.venv` 监听 `127.0.0.1:8000`，Vite 使用 npm 监听 `127.0.0.1:5173`。

Dockerfile、Compose 服务名 `mongo` 和 Volume 均保留为可选兼容方案；本地流程不读取容器服务名、不依赖 Docker Volume，也不会操作已有 Docker 数据。

## 一键启动

安装 MongoDB Server 与 mongosh 并将其加入 PATH 后，从项目根目录运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-all.ps1
```

`start-all.ps1` 复用环境检查、后端和前端脚本。它只在 `.env` 缺失时复制示例配置。默认本地 MongoDB 未运行时，它会启动 `mongod.exe`，并且只使用工作区内的 `.local-mongodb-data` 和 `.local-mongodb-logs`。随后它分别打开两个可见的服务窗口，并在真实 `/ready` 与前端 HTTP 检查通过后报告成功；它不会注册 MongoDB 服务、终止未知端口占用进程或覆盖现有 `.env`。自定义、远程或带认证的 MongoDB URI 不会被脚本自动启动。

## 配置路径

- 根目录 `.env.example`：本地默认 URI、数据库名、超时、CORS 和端口示例。
- `backend/app/core/config.py`：无环境变量时使用 `mongodb://127.0.0.1:27017`；通过源文件位置定位根目录 `.env`，不依赖启动工作目录。
- `frontend/vite.config.js`：浏览器只请求 `/api`；开发代理缺省目标为 `http://127.0.0.1:8000`。
- `backend/requirements.txt`：供助教使用标准 `pip install -r requirements.txt` 安装。

## 启动与检查脚本

- `scripts/check-env.ps1`：检查 Python、Node.js、npm、`.env`、真实 MongoDB ping，以及 8000/5173 端口是否属于本项目服务。它不会安装软件、修改服务或终止进程。
- `scripts/start-backend.ps1`：安全创建 `backend\.venv`，缺依赖时安装 requirements，并用虚拟环境 Python 启动 `app.main:app`。
- `scripts/start-frontend.ps1`：缺少 `node_modules` 时运行 npm install，然后在 `frontend` 工作目录启动 Vite。

脚本保存为带 BOM 的 UTF-8，兼容 Windows PowerShell 5.1 对中文脚本的读取方式。完整首次运行和排错步骤见根目录 README。

## 数据安全与兼容性

后端 lifespan 仍负责创建 PyMongo client、幂等调用 `ensure_indexes()`，并在关闭时释放 client。应用启动和脚本均不清空数据库。Smoke check 仍只允许 `_test` 后缀数据库，只清理本次随机 token 对应的临时记录。原有 `users`、`surveys`、`responses` 设计和五个索引保持不变。
