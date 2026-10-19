# Codex 开发 Prompt 01｜M1 基础设施与项目初始化

你现在是一名负责落地课程项目的全栈工程师。请在**当前工作区**实际创建一个可运行的项目，而不是只输出代码示例或方案。项目是《当代数据管理系统》大作业一：**基于 MongoDB 的问卷系统开发**。此次只实施设计方案中的 **M1：基础设施**。

## 一、设计依据与工作边界

开始前先检查当前工作区，不要覆盖既有项目、不删除现有文件。如存在《第一阶段系统设计方案.md》或 `docs/system-design.md`，**先完整阅读**，以该文件为设计基线；如果原文位于项目根目录，可复制到 `docs/system-design.md`（保留原文）。如果没有找到，不要声称已经阅读，也不要凭空重写这份设计：继续按下方已明确的 M1 约束开展工作，并在最终总结中明确提醒我补入原始设计文档。

设计基线概要：
- 系统采用 **Vue 3 + Vite / Python 3.11+ + FastAPI + Pydantic + PyMongo / MongoDB**，单体后端、REST API、Docker Compose。
- 仅使用 MongoDB 保存业务数据；不引入 MySQL、PostgreSQL、SQLite、Redis、消息队列、微服务、现成问卷系统框架。
- 未来的三个核心集合为 `users`、`surveys`、`responses`。问卷内嵌 `questions[]` 和各题 `rules[]`；回答独立存储。未来模块包括 `auth`、`surveys`、`submissions`、`statistics`、`validation` 和 `rule_engine`。
- M1 只需实现**工程目录、数据库连接、集合和索引初始化、健康检查、最小前端页面、环境配置、可复现启动方式、基础测试与说明文档**。
- **严禁提前实现**注册登录、JWT、问卷 CRUD、题目编辑、答卷提交、统计聚合、校验或跳转业务。这些属于 M2～M5。禁止为了“显得完整”创建不可运行的伪业务接口。
- 不做 UI 美化、复杂组件库、自动生成大批模板文件，不添加业务无关依赖。

## 二、必须实现的项目结构

优先按以下结构创建目录和必要文件。空目录可用 `__init__.py` 或 `.gitkeep` 保留；不要为目录而生成空洞的业务类。

```text
survey-system/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/                # M1 只包含 health 路由
│   │   ├── schemas/            # M2～M5 扩展
│   │   ├── services/           # M2～M5 扩展
│   │   ├── repositories/       # M2～M5 扩展
│   │   ├── core/               # 配置、通用异常
│   │   └── db/                 # Mongo 连接、索引、smoke check
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── views/
│   │   ├── components/
│   │   ├── App.vue
│   │   └── main.js（或 main.ts，选一种且保持一致）
│   ├── Dockerfile
│   ├── package.json
│   └── vite.config.js（或 vite.config.ts）
├── docs/
│   ├── system-design.md       # 仅在找到原始设计文档时复制原文
│   ├── database-design.md     # M1 的集合与索引、设计意图；待实现项显式标明
│   ├── api.md                 # M1 已实现的健康检查接口
│   ├── tests.md               # M1 实际测试步骤、结果；未执行不得写 PASS
│   ├── ai-usage-log.md        # 记录本轮 AI 开发事实，不虚构人工修改
│   └── prompts/              # 如能保存本次完整 Prompt，则存 01-m1-bootstrap.md
├── .env.example
├── .gitignore
├── docker-compose.yml
└── README.md
```

如果当前工作区就是项目根目录，请在当前目录创建上述内容，不再嵌套一层 `survey-system/`；如果当前目录是多个项目的父目录，才新建 `survey-system/`。先检查 Git 状态，**不覆盖、不删除用户现有未提交的文件**，不自行推送远端，也不替用户创建提交（除非当前环境明确授权且任务特别要求；本次没有）。

## 三、FastAPI 后端基础设施

1. 建立能实际启动的 FastAPI 应用，使用模块化路由和应用 lifespan 管理 MongoDB client；配置经由环境变量加载，建议 `pydantic-settings`。
2. 使用 **PyMongo 同步客户端**，避免在 `async def` 路由中直接阻塞调用同步 MongoDB；健康检查涉及同步 DB 调用时可用同步 `def` 路由，由 FastAPI 在线程池执行。M1 不需要 Motor 或额外的异步驱动。
3. 设置合理的 MongoDB 连接超时（如 `serverSelectionTimeoutMS=5000`），数据库不可用时应及时返回可理解的错误，不要无限卡住；关闭应用时关闭 client。
4. 实现以下两个真实接口，统一前缀 `/api/v1`：
   - `GET /api/v1/health/live`：表示 API 进程存活，不依赖数据库；HTTP 200，JSON 中包含服务状态。
   - `GET /api/v1/health/ready`：执行真正的 MongoDB `ping`；成功为 HTTP 200，失败为 HTTP 503。不要把完整异常、连接串、账号或密码回传给浏览器。
5. `/docs` 可以访问 FastAPI 自动生成的 Swagger 文档。
6. 配置 CORS（仅开发时明确的前端地址），不要无理由使用 `allow_origins=["*"]` 与凭证模式的组合。
7. 统一模块导入、配置路径、日志输出，保证直接本地运行和容器运行都能找到模块。

## 四、MongoDB 初始化与索引

在 `backend/app/db/` 中集中实现数据库连接、集合名称常量和可重复执行（幂等）的 `ensure_indexes()`。M1 创建以下索引（名称稳定，重启后不重复报错）：

| Collection | Index | 约束/目的 |
|---|---|---|
| `users` | `username: 1` | 唯一；未来账号注册 |
| `surveys` | `slug: 1` | 唯一；未来分享链接 |
| `surveys` | `owner_id: 1, created_at: -1` | 用户问卷列表 |
| `responses` | `survey_id: 1, submitted_at: -1` | 查询、统计 |
| `responses` | `submission_guard: 1` | 唯一且只索引该字段为字符串的文档，未来禁止重复提交 |

要求：
- 使用 `create_index` + `partialFilterExpression` 等 MongoDB 原生能力，特别注意 `submission_guard` 的部分唯一索引不能错误地限制所有“未填写该字段”的记录。
- 可以创建空集合并建索引，但不要写入模拟的正式用户、问卷或答卷。
- 业务字段级的完整 MongoDB JSON Schema 校验器留待 M2/M3 模型稳定后实现；M1 的 `docs/database-design.md` 要明确解释这一阶段边界，禁止声称完整 Schema 已实现。
- 制作一个**安全且可重复运行**的 MongoDB smoke check：验证 `ping`、索引存在、临时数据的 insert/read/delete；使用独立的临时集合和随机标识，并在 `finally` 中清理，仅触碰自己的临时记录，不清空任何用户数据，不 `dropDatabase`。
- 为后续测试准备专用测试数据库配置；任何实际写入型集成测试都必须先校验目标数据库名是专用测试库（例如以 `_test` 结尾），绝不可写到开发/生产数据中。

## 五、Docker Compose：一条命令启动三项服务

创建根目录 `docker-compose.yml`，至少包含以下服务：

1. `mongo`：使用固定明确版本的 MongoDB 官方镜像（选 MongoDB 7.x 或 8.x 的稳定标签），具备 `mongosh` ping healthcheck、具名 Volume 做数据持久化。
2. `backend`：Python 3.11+、安装 `pyproject.toml` 依赖，启动 Uvicorn 并监听容器内 `0.0.0.0:8000`；通过 Docker 服务名 `mongo` 连接数据库；在 Mongo ready 后启动；可挂载开发代码便于热更新（仅开发用途）。
3. `frontend`：Vue 3 + Vite，Node LTS 镜像，用 npm 和 lockfile 安装依赖，监听容器内 `0.0.0.0:5173`；提供浏览器可访问的页面。

端口默认：
- 前端：`http://localhost:5173`
- 后端：`http://localhost:8000`
- MongoDB 宿主机端口：**127.0.0.1:27018** 映射到容器 27017（可通过 `MONGO_HOST_PORT` 配置）；**不要默认占用本机 27017**，因为可能有已运行的 MongoDB 服务。

要求：
- 配置 Docker 服务内的 Mongo 连接（`mongo:27017`）与宿主机本地调试连接（`localhost:27018`），不要把 `localhost` 错当成容器中的 Mongo 地址。
- 使用 `.env.example` 提供开发示例变量，真正 `.env` 被 `.gitignore` 忽略；示例凭据必须明确标为**仅供本地开发**，绝不作为生产安全配置。不要将真实密码/令牌写入仓库或日志。
- `docker compose up -d --build` 必须能在具有 Docker 的机器上启动；合理使用 `depends_on` 健康依赖、重启策略、Volume 和健康检查，不依赖过时的 `version:` 字段。
- Docker Compose 的停止操作默认不删除 Volume，避免误删数据库历史数据；README 应明确警告 `down -v` 会删除数据。
- 如当前环境无法运行 Docker，请至少验证 `docker compose config`（若 Docker CLI 可用）及各配置文件的静态正确性，并据实说明未实际运行的项目，绝不伪造成功结果。

## 六、Vue 3 + Vite 最小页面

创建一个简洁、可访问的首页即可，包含：
- 项目标题“基于 MongoDB 的问卷系统”；
- 当前“阶段一 · M1 基础环境”提示；
- 一个通过 HTTP 调用 `GET /api/v1/health/ready` 的按钮或自动检测状态显示；连接正常显示“后端与 MongoDB 已就绪”，失败显示错误提示。

使用 Vite dev proxy 将浏览器的 `/api` 请求代理到 `backend:8000`（容器环境）；若支持宿主机单独启动前端，则通过环境变量或明确的开发配置切换代理目标，避免浏览器内直接请求 `http://backend:8000`。

不要在本次任务中实现注册、登录、问卷列表、问卷编辑器或其它业务页面。确保 `npm run build` 可通过。

## 七、README、文档与实际验收

README 以 **Windows PowerShell + Docker Desktop** 作为首选说明，同时给出简洁的跨平台命令。至少包含：
1. 前置条件（Docker Desktop、Docker Compose；本地非容器方式则需要 Python / Node）。
2. 如何把 `.env.example` 复制为 `.env`、修改本地开发凭据与端口；示例使用 `Copy-Item .env.example .env`。
3. 启动 `docker compose up -d --build`、查看状态 `docker compose ps`、查看日志 `docker compose logs -f backend`。
4. 验证前端 `http://localhost:5173`、后端 `/docs`、`/api/v1/health/live` 和 `/api/v1/health/ready`；提供 PowerShell `Invoke-RestMethod` 示例。
5. 如何运行 MongoDB smoke check、后端 pytest、前端 `npm run build`（必要时给出容器内执行方式）。
6. 如何执行 `docker compose down`（保留数据）、如何根据端口冲突调整 `.env`、如何排查 `MongoDB unavailable`、说明 `down -v` 的破坏性。
7. 目前 M1 已实现什么、明确未实现什么、下一步 M2 准备开发什么。

`docs/database-design.md` 写三个集合的预定职责、索引清单和为什么“问卷嵌入题目 / 答案单独存储”；`docs/api.md` 只记录本轮真实实现的两个健康检查接口；`docs/tests.md` 记录本轮可复现测试的命令、输入、预期、**实际结果**；`docs/ai-usage-log.md` 真实记载本轮 AI 生成的代码、使用的任务指令、执行情况、待人工审核点，不得捏造“人工修复”“全部测试通过”。

## 八、测试和最低验收门槛

请尽可能在当前环境**真正执行**以下检查，并给出原始命令、结果摘要、是否通过：

- 后端至少包含健康检查的自动化测试：live 返回 200；模拟数据库不可用时 ready 返回 503；数据库正常时 ready 返回 200。
- MongoDB 集成 smoke check：连接成功；预定索引存在；临时数据插入、读取、清理成功；对任何有风险的数据删除操作加保护。
- `docker compose config` 通过，`docker compose up -d --build` 成功启动（仅在可用环境中执行）。
- `GET /api/v1/health/live` 返回 200；`GET /api/v1/health/ready` 在 Mongo 正常时返回 200。
- Vue 页面能在 `localhost:5173` 打开并显示从后端实际获取的状态（不是硬编码“就绪”）；`npm run build` 成功。
- MongoDB 容器重启或 `docker compose down` 后重新 `up`，具名 Volume 能保留数据（若执行破坏性/重启类操作有风险，先用自己的 smoke 集合测试，绝不删除用户已有数据）。

若环境条件不足以运行全部测试，**把未执行明确标为 NOT RUN**，给出我在本地可复制的命令，不得把静态检查当成真实端到端成功。

## 九、执行方式与最终汇报格式

请直接落地代码，遵循：**检查现状 → 简述不超过 10 行的实现计划 → 修改文件 → 测试 → 更新文档 → 汇报**。不要仅返回“建议这样写”的代码块，也不要擅自大规模重构已有代码。

最终回复必须包含：
1. 本次创建/修改的目录与关键文件清单；
2. 真实执行过的命令与结果（PASS / FAIL / NOT RUN）；
3. 一套能够在我 Windows PowerShell 中直接复制执行的**最简启动与验证命令**；
4. 已完成的 M1 功能、仍未实现的 M2～M5 功能；
5. 遇到的问题、采用的实际解决方案、风险或偏离设计之处；
6. 需要我亲自检查的项目和下一步 M2 建议。

**成功标准：** 我在本地复制 `.env`、运行 `docker compose up -d --build` 后，可以打开 Vue 首页、访问 FastAPI `/docs`、调用两个健康检查接口；后端真正连通 MongoDB，目标索引已经创建；基础测试与文档可复现。仅实现 M1，绝不提前实现问卷业务。
