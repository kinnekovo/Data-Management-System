# MongoDB 数据库设计

## 1. 设计原则

默认数据库为 `survey_system`，包含 `users`、`surveys`、`responses` 三个集合。问卷定义嵌入 `surveys.questions`，因为题目、选项和跳转规则总是随问卷整体读取；答卷独立保存，避免持续增长的数据把单个问卷文档推向 MongoDB 16 MB 上限。

MongoDB 文档模型适合承载不同题型的异构 `validation`、`options` 和 `rules`。用户、问卷和答卷之间使用 ObjectId 引用，应用层负责权限与跨文档业务规则，数据库 Schema 负责稳定字段类型，索引负责唯一性和主要查询性能。

MongoDB 可执行 Schema 与索引均定义在 `backend/app/db/schema.py`。应用启动和演示数据脚本通过 `ensure_database_schema()` 幂等应用集合验证器与索引。

## 2. 集合关系

```mermaid
erDiagram
    USERS ||--o{ SURVEYS : creates
    USERS ||--o{ RESPONSES : submits
    SURVEYS ||--o{ RESPONSES : receives
    SURVEYS ||--|{ QUESTIONS : embeds

    USERS {
        ObjectId _id
        string username
        string password_hash
        date created_at
    }
    SURVEYS {
        ObjectId _id
        ObjectId owner_id
        string slug
        string status
        array questions
        int definition_version
    }
    RESPONSES {
        ObjectId _id
        ObjectId survey_id
        ObjectId respondent_id
        array answers
        string submission_guard
        date submitted_at
    }
```

## 3. `users` 集合

```json
{
  "_id": "ObjectId",
  "username": "alice",
  "password_hash": "$argon2id$...",
  "created_at": "UTC Date"
}
```

必需字段：`username`、`password_hash`、`created_at`。系统只保存 Argon2 哈希，不保存明文密码。

## 4. `surveys` 集合

```json
{
  "_id": "ObjectId",
  "owner_id": "ObjectId(users)",
  "slug": "公开随机标识",
  "title": "课程体验调查",
  "description": "...",
  "allow_anonymous": false,
  "allow_multiple_submissions": false,
  "status": "draft | published | closed",
  "expires_at": null,
  "questions": [
    {
      "id": "q_xxx",
      "type": "single_choice | multiple_choice | text | number",
      "title": "...",
      "required": true,
      "options": [{"id": "opt_xxx", "label": "..."}],
      "validation": {},
      "rules": [{
        "priority": 1,
        "operator": "eq",
        "value": "opt_xxx",
        "target_question_id": "q_yyy"
      }]
    }
  ],
  "schema_version": 1,
  "definition_version": 1,
  "created_at": "UTC Date",
  "updated_at": "UTC Date",
  "published_at": "UTC Date | null",
  "closed_at": "UTC Date | null"
}
```

题目和选项使用稳定随机 ID，因此调整数组顺序不会破坏规则和统计引用。发布后冻结定义；`definition_version` 写入答卷，为后续不可变版本快照预留扩展点。

## 5. `responses` 集合

```json
{
  "_id": "ObjectId",
  "survey_id": "ObjectId(surveys)",
  "respondent_id": "ObjectId(users)",
  "definition_version": 1,
  "answers": [
    {"question_id": "q_xxx", "value": "opt_xxx"},
    {"question_id": "q_yyy", "value": ["opt_a", "opt_b"]},
    {"question_id": "q_zzz", "value": 88}
  ],
  "submission_guard": "<survey_id>:<respondent_id>",
  "submitted_at": "UTC Date"
}
```

允许重复提交时不写 `submission_guard`；禁止重复时写入稳定字符串。匿名语义是“对创建者隐藏身份”而非免登录，因此数据库仍保存 `respondent_id`，以执行认证与重复策略。

## 6. 索引设计

| 集合 | 索引 | 属性 | 用途 |
|---|---|---|---|
| `users` | `{username: 1}` | 唯一 | 防止重复用户名并支持登录查询 |
| `surveys` | `{slug: 1}` | 唯一 | 公开链接查询 |
| `surveys` | `{owner_id: 1, created_at: -1}` | 普通 | 创建者工作台倒序列表 |
| `responses` | `{survey_id: 1, submitted_at: -1}` | 普通 | 原始答卷分页和统计过滤 |
| `responses` | `{submission_guard: 1}` | 唯一部分索引 | 仅约束字符串 guard，并发防重 |

## 7. 校验分层与一致性

- MongoDB `$jsonSchema` 校验稳定必需字段、BSON 类型、状态枚举和主要长度；
- Pydantic 校验 HTTP 输入的基本类型、长度和数组规模；
- 服务层校验题型约束、规则目标、顺序关系和实际访问路径；
- 发布后冻结定义，避免答卷和题目版本失配；
- 统计从原始答卷实时聚合，不维护可能过期的冗余计数；
- 日期统一保存为 UTC，并以 ISO 8601 返回 API。

## 8. 测试与演示数据安全

集成测试只允许随机且以 `_test` 结尾的数据库，会话结束后只删除该随机库。演示脚本只接受 `_demo` 后缀，并只替换带 `stage1_demo_v1` 标记的数据。启动、Schema 初始化和索引初始化都不会清空业务集合。
