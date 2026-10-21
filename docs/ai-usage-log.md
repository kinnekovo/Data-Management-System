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
- 后续补充：新增 `scripts/start-all.ps1`，将配置准备、环境检查、MongoDB、后端、前端、健康等待和浏览器打开组合为一次命令；复用已有三个脚本，不修改 M1 API 或问卷业务。发现本机已安装 MongoDB 8.3.1 但未注册 Windows 服务，因此增加默认本地 URI 下的项目专用 `mongod` 启动逻辑。实际从三个端口均空闲的状态启动成功；`mongosh ping`、`live`、`ready` 和前端 HTTP 均通过。
- 人工审核状态：尚未进行；没有虚构人工修改、Git 提交或 M2 功能。

## 2026-10-19 · Codex · 第一阶段完整业务开发

- 授权与范围：用户明确授权继续注册、问卷、填写、跳转和统计；基线来自工作区设计文档、课程 `大作业一第一阶段.docx` 和任务附件 `goal-objective.md`。只实现第一阶段闭环，没有加入团队协作、文件题、导出或第二阶段扩展。
- 后端修改：增加 Argon2 密码哈希、JWT 注册登录、owner 权限隔离、问卷及题目 CRUD、发布/关闭、四题型校验、前向规则引擎、服务端路径重放、匿名/重复/截止策略、原始答卷分页和 MongoDB 实时聚合统计；保留同步 PyMongo 与 lifespan 连接管理。
- 数据设计：沿用 `users`、`surveys`、`responses` 集合；增加稳定题目/选项 ID、定义版本和并发重复提交 guard；启动索引幂等，不清空业务库。
- 前端修改：Vue Router 页面覆盖注册、登录、工作台、新建/编辑、可视化规则、逐题填写、检查提交和统计；所有 API 统一由客户端模块访问，并补齐加载、空、错误和响应式状态。
- 启动与演示：一键脚本继续作为默认入口，并补充检查 PyJWT/pwdlib 依赖；新增受 `_demo` 后缀与 marker 双重保护的演示数据脚本。
- 实际问题：首次尝试安装新增 Python 依赖受到沙箱网络限制，经批准后成功；课程 DOCX 文本可读取，但环境缺少 LibreOffice，因此没有完成 DOCX 页面渲染检查；浏览器测试发现分支进入多选题时 Vue 模型退化为布尔值，改为显式维护选项 ID 数组并重新端到端验证；Docker CLI 读取用户 config 文件时提示权限警告，但 Compose 配置解析退出码为 0。
- 实际验证：真实 MongoDB 下后端最终 41 tests passed；Vite 生产构建 41 modules；环境检查、live、ready、Vite 代理和 `start-all.ps1 -NoBrowser` 通过；演示库写入与非 `_demo` 拒绝护栏通过；两账号浏览器闭环完成，统计结果与保存路径一致。
- 数据处理：集成测试仅删除随机 `_test` 库；演示后只删除本次创建的 `survey_system_codex_demo`。浏览器验收数据保留在默认开发库供人工复查，没有清理或覆盖其他数据。
- 人工审核与版本控制：尚未人工审核；没有自动创建 Git 提交或标签。

## 2026-10-20 · Codex · 多选跳转匹配值修复

- 用户反馈：多选题条件规则的匹配值不能自由组合，无法表达“同时包含 A 和 B”或“A、B 至少一个”。
- 根因：题型切换和新增选项在前端使用空 ID，规则复选框因此被禁用；动态复选框还直接依赖 `v-model` 数组，存在退化为共享布尔状态的风险。
- 修复：客户端为新增选项立即生成稳定 `opt_` ID；添加规则和保存前补齐遗留空 ID；规则复选框改为显式复制、增删选项 ID 的数组更新。
- 实测：Vite 构建通过；真实浏览器分别保存 `contains_all=[A,B]` 与 `contains_any=[A,C]`，MongoDB 文档与界面勾选状态一致。专用回归草稿无答卷，核对 ID、标题和 owner 后清理。

## 2026-10-21 · Codex · 测试用例与手工测试文档

- 任务：为创建问卷、添加题目、跳转逻辑、答案校验、提交问卷和统计结果编写自动测试，并形成含步骤、输入、输出和结果的手工测试流程。
- 自动测试：新增 `backend/tests/integration/test_required_cases.py`，把六个课程验收项拆成独立的真实 MongoDB API 集成测试；继续使用随机 `_test` 数据库并在会话结束后清理。
- 测试文档：新增 `docs/test-cases.md`，记录六个自动用例的实际输出，以及九个浏览器手工用例、预期结果和执行记录模板；未执行的手工项明确标为 `NOT RUN`。
- 实际问题：首次运行时本机 27017 未监听；启动工作区 `.local-mongodb-data` 对应的项目专用 MongoDB 后，沙箱进程仍无法连接，随后在获准的本机执行环境中完成真实数据库测试。
- 实测：新增核心用例 `6 passed`；完整后端回归 `47 passed`；Vite 8.3.4 生产构建成功（41 modules）。pytest 有 1 条 Starlette TestClient/AnyIO 上游弃用警告，不影响测试结果。
