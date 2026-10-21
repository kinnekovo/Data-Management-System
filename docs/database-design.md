# MongoDB 数据库设计

默认数据库 `survey_system` 包含 `users`、`surveys`、`responses` 三个集合。问卷定义嵌入 `surveys.questions`，答卷独立存放。这样读取和发布一份完整问卷只需单文档操作，同时避免持续增长的答卷把问卷文档推向 MongoDB 16 MB 上限。

MongoDB 适合本项目，因为不同题型的 `validation`、`options` 和 `rules` 字段结构不同，文档模型可以把一次使用时总是一起读取的问卷定义整体保存；新增题型约束不需要频繁拆表迁移。若采用关系模型，题目、选项、规则和不同答案值通常需要多表关联或类型表，强约束更明确，但读取完整问卷和演进异构题型更繁琐。用户、问卷、答卷仍通过 ObjectId 引用，并由应用层权限校验和索引保证本阶段的一致性。

## users

```json
{
  "_id": "ObjectId",
  "username": "alice",
  "password_hash": "$argon2id$...",
  "created_at": "UTC Date"
}
```

索引：`username` 唯一。系统只保存 Argon2 哈希，不保存或记录明文密码。

## surveys

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
  "schema_version": 1,
  "definition_version": 1,
  "questions": [
    {
      "id": "q_xxx",
      "type": "single_choice | multiple_choice | text | number",
      "title": "...",
      "required": true,
      "options": [{"id":"opt_xxx","label":"..."}],
      "validation": {},
      "rules": [{
        "priority": 1,
        "operator": "eq",
        "value": "opt_xxx",
        "target_question_id": "q_yyy"
      }]
    }
  ],
  "created_at": "UTC Date",
  "updated_at": "UTC Date",
  "published_at": "UTC Date | null",
  "closed_at": "UTC Date | null"
}
```

索引：`slug` 唯一，`{owner_id:1, updated_at:-1}`。题目与选项采用稳定随机 ID，重排时 ID 不变，因此答卷、规则和统计不会依赖数组位置。当前阶段发布后冻结定义，`definition_version` 仍写入每份答卷，为后续版本演进保留一致性边界。

## responses

```json
{
  "_id": "ObjectId",
  "survey_id": "ObjectId(surveys)",
  "respondent_id": "ObjectId(users)",
  "definition_version": 1,
  "answers": [
    {"question_id":"q_xxx","value":"opt_xxx"},
    {"question_id":"q_yyy","value":["opt_a","opt_b"]},
    {"question_id":"q_zzz","value":88}
  ],
  "submission_guard": "<survey_id>:<respondent_id> | null",
  "submitted_at": "UTC Date"
}
```

索引：

- `{survey_id:1, submitted_at:-1}`：创建者分页查看答卷；
- `{survey_id:1, respondent_id:1}`：按问卷和填写者查询；
- `submission_guard` 唯一、稀疏：仅禁止重复的问卷写入字符串；允许重复时字段为 null/缺省，因此并发提交不会误冲突。

匿名语义是“对问卷创建者隐藏身份”，不是“无需登录”。数据库保留 `respondent_id` 以校验令牌、截止时间和重复策略；API 序列化匿名问卷答卷时移除 `respondent_id` 与用户名。

## 一致性与聚合

- 启动时 `ensure_indexes` 重复创建同名同定义索引，具有幂等性，不删除数据。
- 发布时完整校验定义；发布后不允许修改题目、选项、规则与填写策略。
- 提交时服务端重新计算访问路径，只保存路径内答案；跳过的必答题不报错，伪造的路径外答案被拒绝。
- 单选/多选用 `$unwind + $group` 统计，数字题用 `$avg/$min/$max`，文本和原始答卷分页读取；结果来自真实持久化数据，不保存易过期的冗余汇总。
- 数据库操作全部使用 UTC；API 输出 ISO 8601 字符串。

## 安全的测试和演示库

集成测试只允许数据库名以 `_test` 结尾，并为每次运行生成随机名称，结束后只删除该名称。演示脚本只接受 `_demo` 后缀，并只替换带 `stage1_demo_v1` 标记的文档。应用启动、索引初始化和脚本均不会清空默认业务库。
