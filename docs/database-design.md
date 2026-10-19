# M1 数据库设计

M1 只建立连接、集合入口和索引，不写入正式业务数据。完整字段级 MongoDB JSON Schema 校验器将在 M2/M3 模型稳定后实现；当前不能宣称完整 Schema 已落地。

默认运行方式已调整为 Windows 本地 MongoDB，连接参数从项目根目录 `.env` 读取，缺省 URI 为 `mongodb://127.0.0.1:27017`，开发数据库仍为 `survey_system`。Docker Compose 只作为可选兼容方式，容器内仍使用 `mongo:27017`；此次调整没有修改集合、字段规划或索引定义。

## 集合职责

| 集合 | 预定职责 | M1 状态 |
|---|---|---|
| `users` | 用户名、密码哈希与注册时间 | 仅建立唯一索引 |
| `surveys` | 一份完整问卷定义，内嵌 `questions[]` 与各题 `rules[]` | 仅建立分享及列表索引 |
| `responses` | 一次完整答卷，通过 `survey_id` 引用问卷 | 仅建立查询及重复提交保护索引 |

题目和规则随问卷定义共同读取、共同发布，适合嵌入 `surveys`；答卷会持续增长，必须独立存储，避免问卷文档无限增大。M1 不创建模拟用户、问卷或答卷。

## 已实现索引

| 集合 | 键 | 名称 | 约束/用途 |
|---|---|---|---|
| `users` | `{username: 1}` | `ux_users_username` | 唯一用户名 |
| `surveys` | `{slug: 1}` | `ux_surveys_slug` | 唯一分享标识 |
| `surveys` | `{owner_id: 1, created_at: -1}` | `ix_surveys_owner_created` | 用户问卷列表 |
| `responses` | `{survey_id: 1, submitted_at: -1}` | `ix_responses_survey_submitted` | 答卷查询与统计 |
| `responses` | `{submission_guard: 1}` | `ux_responses_submission_guard` | 唯一且仅索引字段类型为字符串的文档 |

最后一项使用 `partialFilterExpression: {submission_guard: {$type: "string"}}`，所以未来允许重复填写时省略该字段，不会因多个缺失值触发唯一冲突。`ensure_indexes()` 使用固定名称，可重复执行。

## Smoke check 安全边界

`python -m app.db.smoke_check` 只连接 `MONGODB_TEST_DATABASE`，且数据库名必须以 `_test` 结尾。它执行 `ping`、建立并核对上述 5 个索引，在 `_m1_smoke` 中插入带随机 token 的临时文档，读回后在 `finally` 中按 token 删除。连接失败或尚未插入时不会执行删除，也不使用 `dropDatabase`、`dropCollection` 或无条件删除。
