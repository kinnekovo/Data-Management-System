# 第一阶段测试说明与实测结果

课程验收所需的逐项测试步骤、输入、预期输出、实际输出和结果，见 [test-cases.md](test-cases.md)。

测试日期：2026-10-19 至 2026-10-21。环境：Windows、Python 3.13.9、Node.js 24.19.0、npm 11.17.0、MongoDB 8.3.1。以下结果均来自本机实际命令或真实浏览器操作。

## 自动化覆盖

### 单元测试

`backend/tests/unit/test_validation.py` 覆盖：

- 单选等于、多选包含任一/全部；
- 数字 eq/gt/gte/lt/lte；
- 必答、选项合法性、多选重复、最少/最多选择；
- 文本长度、数字类型/整数/范围、NaN 与正负无穷；
- 发布定义错误、规则优先级、目标存在性和只允许向后跳转；
- 路径重放、跳过必答题、路径外伪造、重复和未知题号。

### 真实 MongoDB 集成测试

`backend/tests/integration/test_business_api.py` 使用运行中的真实 MongoDB，不使用 mock。每次创建随机 `_test` 数据库，校验后只删除该数据库。覆盖：

- 注册、重复用户名、正确/错误登录、无效与过期 JWT；
- owner 隔离、问卷列表、题目新增/修改/删除/重排；
- 空问卷发布失败、发布冻结、关闭、截止时间；
- 四题型、前向分支、路径外答案、类型错误；
- 允许重复提交；禁止重复时两个并发请求实际得到 201 和 409；
- 非匿名身份可见、匿名 API 身份隐藏但数据库保留策略字段；
- 选择计数含零项、跳过题回答数、数字聚合、文本与答卷分页。

### 业务用例矩阵

下表的“实际”来自上述 pytest 对真实 MongoDB 的运行结果；每一行均为 PASS。

| 场景 | 关键输入/步骤 | 预期 | 实际 |
|---|---|---|---|
| 注册与登录 | 同名注册、错误密码、非法/过期 JWT | 409、401、401 | 返回对应状态与统一错误码 |
| 权限隔离 | B 读取 A 的问卷/统计 | 不泄露资源 | 均返回 404，B 列表无 A 问卷 |
| 草稿属性 | PATCH description | 保存修改 | 200，详情返回新说明 |
| 草稿填写 | 用 slug 获取未发布问卷 | 拒绝 | 409 `SURVEY_NOT_PUBLISHED` |
| 题目管理 | 添加两题、重排、删除未引用题 | ID 稳定且顺序更新 | 200/204，详情只剩预期题目 |
| 无效发布 | 空问卷；规则目标缺失/向前；优先级重复 | 拒绝发布/定义 | 422 或纯逻辑 issues 含对应错误 |
| 规则运算符 | single eq；multi any/all；number eq/gt/gte/lt/lte 边界 | 匹配结果正确 | 参数化测试全部符合预期 |
| 顺序与跳过 | 规则未命中、可选题未答、跳过必答题 | 顺序前进；跳过题无需答案 | 重放路径分别符合预期 |
| 路径防伪造 | 添加被跳过题、未知 ID、重复 ID | 拒绝 | 422 / `ANSWER_OUTSIDE_PATH`、`UNKNOWN_QUESTION`、`DUPLICATE_QUESTION` |
| 单选校验 | 非选项 ID | 拒绝 | `INVALID_ANSWER` |
| 多选校验 | 少选、多选、重复、未知 ID | 拒绝 | 分别命中数量/重复/未知错误 |
| 文本校验 | 过短、过长、必答纯空格 | 拒绝 | 全部命中对应错误 |
| 数字校验 | 字符串、bool、越界、非整数、NaN/Infinity | 拒绝 | 全部命中对应错误 |
| 合法分支提交 | q1 跳 q3，提交 q1/q3/q4 | 只保存访问路径 | 201，visited IDs 为 q1/q3/q4 |
| 允许重复 | 同一用户同一问卷连续提交两次 | 两次成功、两份文档 | 201 + 201，total=2 |
| 禁止重复并发 | 同一用户两个线程同时提交 | 至多一次成功 | 实际排序状态为 `[201, 409]`，只存 1 份 |
| 匿名/非匿名 | 分别查看原始答卷 | 匿名隐藏身份，非匿名显示用户名 | 字段序列化符合预期；匿名库内仍有策略 ID |
| 状态控制 | 发布后改标题、关闭后提交、已截止提交 | 拒绝 | 409；截止返回 `SURVEY_EXPIRED` |
| 空数据统计 | 发布后尚未提交 | 总数/回答数 0，数字平均 null，选项 0 | 聚合返回预期空值 |
| 有数据统计 | 两条不同路径答卷 | 计数、跳题人数、均值正确 | 文本题 1 人，数字均值 30，多选计数 1/2/0 |
| 分页 | 文本详情 page_size=1、原始答卷列表 | 总数与单页内容正确 | 文本 total=1；答卷 total=2 |

## 实测矩阵

| 状态 | 检查 | 实际结果 |
|---|---|---|
| PASS | `python -m pytest -q` | 2026-10-21 最终复测 47 passed；1 条来自 Starlette TestClient/AnyIO 的上游弃用警告 |
| PASS | `npm run build` | 最终复测：Vite 8.3.4，41 modules，225 ms，生成 dist |
| PASS | `check-env.ps1` | Python、Node、npm、`.env`、MongoDB ping、8000/5173 服务识别全部通过 |
| PASS | 后端 live/ready | `alive`；`ready` 且 `database=connected` |
| PASS | 后端启动脚本与当前源码 | `start-backend.ps1 -Port 18124` 成功；OpenAPI 1.0.0、ready/数据库 connected；验证后停止该实例 |
| PASS | Vite API 代理 | `http://127.0.0.1:5173/api/v1/health/ready` 返回 ready |
| PASS | 一键启动脚本复用已有服务 | `start-all.ps1 -NoBrowser` 退出码 0，识别 MongoDB、FastAPI、Vue 均已就绪 |
| PASS | Docker 配置（可选） | `docker compose config --quiet` 退出码 0；仅出现用户 Docker config 文件无权限警告 |
| PASS | 演示种子 | 独立 `_demo` 库写入 2 用户、1 问卷、1 答卷，三集合索引存在 |
| PASS | 演示护栏 | 对 `survey_system` 执行种子被明确拒绝，退出码 1，默认库未修改 |
| PASS | 索引初始化幂等 | 在独立 `_test` 库连续执行两次 `ensure_indexes`，索引集合稳定，随后仅删除该测试库 |
| PASS | 浏览器完整闭环 | 注册创建者和填写者、4 题编辑、规则、发布、分支填写、提交、统计均成功 |
| PASS | 浏览器分支 | 选择“有经验”从第 1 题跳到第 3 题，检查页显示共访问 3 题 |
| PASS | 浏览器统计 | 1 份提交；文本题 0 人；单/多选计数正确；数字均值/最小/最大均为 90；显示非匿名用户名 |
| PASS | 桌面/窄屏布局 | 1280×900 与默认窄屏均实际截图检查，无横向溢出或页面崩溃 |
| NOT RUN | MongoDB 进程重启持久化 | 可确认 27017 为 `mongod.exe`，但当前权限无法读取进程命令行以证明其 `dbPath` 属于本项目；为避免误停其他 MongoDB 实例，没有执行重启 |
| NOT RUN | 全新机器首次依赖下载 | 当前工作区依赖已安装；未用另一台干净 Windows 机器复测网络下载 |
| NOT RUN | Docker 容器完整启动 | Docker 守护进程管道拒绝当前用户访问；Docker 不是默认部署，已完成 Compose 静态解析但未启动容器 |

演示验证结束后只删除了本次创建的 `survey_system_codex_demo`，没有删除默认业务库或其他 MongoDB 数据。
最终数据库清单仍包含原工程已有/配置中的 `survey_system_test`；本任务没有删除它。每次集成测试生成的随机 `_test` 数据库均已由 fixture 清理。

## 运行命令

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest -q

Set-Location ..\frontend
npm run build

Set-Location ..
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-env.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-all.ps1 -NoBrowser
```

## 人工回归重点

1. 用两组新账号完成创建者/填写者切换；
2. 修改前置答案后返回，确认不再可达题目的旧答案不出现在检查页；
3. 匿名问卷提交后检查管理端不显示用户名；
4. 用两个并发请求验证禁止重复时只保存一份；
5. MongoDB 停止时确认 live 仍说明进程状态，ready 返回非成功且前端显示错误。

## 2026-10-20 多选跳转编辑器回归

针对“匹配值无法自由勾选”执行真实浏览器验证：新建三题草稿，首题为 A/B/C 多选题；规则 1 选择 `contains_all` 并仅勾选 A+B，规则 2 选择 `contains_any` 并仅勾选 A+C。界面分别显示 `1/1/0` 与 `1/0/1`，保存后 MongoDB 中两条规则的 `value` 分别为对应的两个稳定选项 ID。结果 PASS。测试草稿无答卷，按精确 ID、标题和 owner 校验后已清理。

## 2026-10-21 课程验收核心用例

新增 `backend/tests/integration/test_required_cases.py`，将创建问卷、添加题目、跳转逻辑、答案校验、提交问卷和统计拆分为 6 个可独立定位的 API 集成测试。测试连接项目专用本地 MongoDB，使用随机 `_test` 数据库并由 fixture 在会话结束后删除。定向执行结果：`6 passed`；1 条 Starlette TestClient/AnyIO 上游弃用警告，不影响结果。
