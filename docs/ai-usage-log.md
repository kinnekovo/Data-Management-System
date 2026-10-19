# AI 使用记录

## 2026-10-19 · Codex · M1 基础环境

- 任务：完整阅读设计基线和 `Codex_M1_基础环境搭建_Prompt.md.md`，只实现 M1。
- Prompt：原始完整指令已原样保存于 `docs/prompts/01-m1-bootstrap.md`。
- 生成/修改：FastAPI 配置、lifespan、Mongo 连接与索引、健康路由、安全 smoke check、pytest；Vue/Vite 状态页；Dockerfile、Compose、环境示例、README 与 M1 文档。
- 实际执行：安装固定依赖，运行 Python 编译、6 项 pytest、Compose 配置解析、npm 构建与真实 Uvicorn HTTP 检查；本机同时启动 Uvicorn/Vite 并在浏览器确认前端读取真实 503 状态；尝试启动 Docker Compose 和执行 Mongo smoke check。
- 发现并修正：为中文路径下系统 Python 创建 venv 失败，改用 Codex 内置 Python 3.12 与 uv；Docker Compose 项目名由中文目录推导失败，增加固定 `name: survey-system`；初始 Vite 版本审计出现漏洞，升级到审计为 0 漏洞的当前版本；修正 smoke check 在插入前连接失败仍尝试删除的问题。
- 未声称成功：Docker Hub 拉取返回 EOF，MongoDB smoke、Mongo ready 200、浏览器三端联调和 Volume 持久化均未完成，详见 `docs/tests.md`。
- 人工审核状态：尚未进行；没有虚构人工修改或 Git 提交。
- M1 边界：未生成注册、JWT、问卷 CRUD、题目、答卷、统计、校验或跳转代码。

## 2026-10-19 · Codex · M1 本地原生部署调整

- 修改背景：为方便课程助教验收，将默认启动方式由 Docker Compose 改为 Windows 本地 MongoDB + Python 虚拟环境 + npm；Docker 保留为可选兼容方式。
- 实际修改：默认 URI 改为 `mongodb://127.0.0.1:27017`；配置从项目根目录 `.env` 稳定读取；新增 `backend/requirements.txt`、三个 PowerShell 脚本、本地部署文档和配置测试；重写 README 的安装、启动、验收和排错章节。
- 保留内容：PyMongo 同步驱动、lifespan、两个健康接口、三个集合规划、五个索引、测试库 smoke 安全保护和 Vue 连通性页面均未重构。
- 实际问题与修正：Windows PowerShell 5.1 需要 UTF-8 BOM 才能正确解析中文脚本；原生命令的 stderr 会被 `ErrorActionPreference=Stop` 提前转成异常；Vite 页面中文标题受 PowerShell 响应编码影响。分别通过 BOM、按进程退出码判断和 ASCII 页面结构标记解决。
- 实际验证：本机 MongoDB Community 8.3.1 以隔离工作区数据目录监听 27017；启动脚本创建 Python 3.13 虚拟环境并安装 requirements；FastAPI 和 Vite 原生启动；真实 ready 200、5 索引 smoke、8 项 pytest、前端构建、环境脚本和浏览器“已就绪”状态均通过。
- 数据处理：未删除或覆盖任何既有 MongoDB 数据、Docker Volume 或项目文件；测试 Mongo 只使用 `.local-mongodb-data` 和 `survey_system_test`，smoke 临时记录已清理。
- 人工审核状态：尚未进行；没有虚构人工修改、Git 提交或 M2 功能。
