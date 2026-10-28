# 第二阶段 API 文档

基地址：`http://127.0.0.1:8000/api/v1`。除注册、登录和健康检查外，所有接口都需要：

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

成功响应直接返回资源。业务错误统一为：

```json
{"code":"SURVEY_NOT_FOUND","message":"问卷不存在","details":null}
```

参数校验失败使用 `VALIDATION_ERROR` 和 HTTP 422。常用状态码：200 查询/更新成功，201 创建/提交成功，204 删除成功，401 未登录或令牌无效，404 资源不存在（所有权隔离也返回 404），409 状态或唯一约束冲突，422 定义/答案无效，503 MongoDB 未就绪。

## 健康检查

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health/live` | 仅检查后端进程，返回 `{"status":"alive"}` |
| GET | `/health/ready` | 真实执行 MongoDB ping；成功返回 ready，失败返回 503 |

## 账号

| 方法 | 路径 | 请求体 / 结果 |
|---|---|---|
| POST | `/auth/register` | `{"username":"alice","password":"SecurePass123"}`；201 |
| POST | `/auth/login` | 同上；返回 `access_token`、`token_type`、`expires_at` 和用户信息 |
| GET | `/auth/me` | 返回当前用户 `id`、`username`、`created_at` |

用户名只允许中文、字母、数字、下划线和连字符，长度 3–32；密码长度 8–128。重复用户名返回 409 `USERNAME_EXISTS`，错误密码返回 401 `INVALID_CREDENTIALS`。

## 问卷与题目（仅创建者）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/surveys` | 创建草稿 |
| GET | `/surveys` | 当前用户问卷列表 |
| GET | `/surveys/{survey_id}` | 问卷定义 |
| PATCH | `/surveys/{survey_id}` | 修改草稿基本信息 |
| POST | `/surveys/{survey_id}/questions` | 新增题目 |
| PATCH | `/surveys/{survey_id}/questions/{question_id}` | 修改题目 |
| DELETE | `/surveys/{survey_id}/questions/{question_id}` | 删除未被规则引用的题目；204 |
| PUT | `/surveys/{survey_id}/question-order` | 按完整 ID 数组重排 |
| POST | `/surveys/{survey_id}/publish` | 校验完整定义并发布，生成分享 slug |
| POST | `/surveys/{survey_id}/close` | 关闭已发布问卷 |

创建问卷示例：

```json
{
  "title": "课程体验调查",
  "description": "第一阶段演示",
  "allow_anonymous": false,
  "allow_multiple_submissions": false,
  "expires_at": null
}
```

题目通用结构：

```json
{
  "type": "single_choice",
  "title": "是否使用过 MongoDB？",
  "required": true,
  "options": [{"label":"使用过"},{"label":"尚未使用"}],
  "validation": {},
  "rules": []
}
```

题型与约束：

- `single_choice`：至少 2 个选项，答案为选项 ID。
- `multiple_choice`：至少 2 个选项；可设 `min_selections`、`max_selections`，答案为无重复选项 ID 数组。
- `text`：可设 `min_length`、`max_length`，答案必须为字符串。
- `number`：可设 `min_value`、`max_value`、`integer_only`，答案必须是 JSON 数字，字符串数字和非有限值无效。

创建、详情、发布和关闭返回同一问卷资源形状（列表省略 `questions`）：

```json
{
  "id":"...","slug":"...","title":"课程体验调查","description":"...",
  "allow_anonymous":false,"allow_multiple_submissions":false,
  "status":"draft","expires_at":null,"question_count":0,"questions":[],
  "schema_version":1,"definition_version":1,
  "created_at":"...Z","updated_at":"...Z","published_at":null,"closed_at":null,
  "share_path":"/survey/<slug>"
}
```

新增/修改题目返回带后端生成稳定 `id` 和选项 `id` 的题目；重排返回 `{"questions":[...]}`；删除成功无响应体。

跳转规则示例：

```json
{
  "priority": 1,
  "operator": "eq",
  "value": "opt_yes",
  "target_question_id": "q_features"
}
```

支持 `eq`、`contains_any`、`contains_all`、`gt`、`gte`、`lt`、`lte`。按较小 priority 优先命中，只允许跳到后续题目；后端发布时检查目标、操作符、条件值与重复优先级。发布后定义被冻结。

## 填写

填写者也必须登录。公开路径不会暴露 owner ID 或内部隐私字段。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/public/surveys/{slug}` | 获取可填写的已发布问卷 |
| POST | `/public/surveys/{slug}/responses` | 提交答卷；201 |

提交示例：

```json
{
  "answers": [
    {"question_id":"q_experience","value":"opt_yes"},
    {"question_id":"q_features","value":["opt_document","opt_index"]},
    {"question_id":"q_score","value":90}
  ]
}
```

服务端按已保存的定义重新执行路径，校验每个路径内必答题、数据类型、边界和选项，并拒绝重复题号、未知题号以及路径外伪造答案。问卷关闭或到期返回 409。禁止重复提交时，`responses.submission_guard` 的唯一索引保证并发下只有一个请求成功。

提交成功示例：

```json
{"response_id":"...","submitted_at":"...Z","visited_question_ids":["q_experience","q_features","q_score"]}
```

## 响应与统计（仅创建者）

| 方法 | 路径 | 查询参数 / 说明 |
|---|---|---|
| GET | `/surveys/{id}/responses` | `page`、`page_size`；原始答卷分页 |
| GET | `/surveys/{id}/statistics` | 提交总数和各题实时汇总 |
| GET | `/surveys/{id}/statistics/questions/{question_id}` | 文本题分页详情；`page`、`page_size` |

单选和多选返回每个选项计数（包括 0）；数字题返回 `average`、`minimum`、`maximum`，无答案时为 null；文本题汇总只返回回答数，详情单独分页。匿名问卷响应列表不序列化填写者 ID 和用户名，数据库仍保留 respondent ID 以执行登录和重复提交策略。

整卷统计示例：

```json
{
  "survey_id":"...","title":"课程体验调查","submission_count":2,
  "question_stats":[
    {"question_id":"q1","title":"是否使用过？","type":"single_choice","answered_count":2,
     "options":[{"id":"yes","label":"是","count":1},{"id":"no","label":"否","count":1}]},
    {"question_id":"q2","title":"评分","type":"number","answered_count":1,
     "average":90,"minimum":90,"maximum":90}
  ]
}
```

分页响应均返回 `page`、`page_size`、`total`、`items`。非匿名原始答卷 item 含 `respondent_id` 与 `respondent_username`；匿名问卷不含这两个键。

## 题目库、版本和共享

| 方法 | 路径 | 说明 |
|---|---|---|
| POST / GET | `/questions` | 创建题目或查询个人/共享题目，`scope=all|mine|shared` |
| GET / DELETE | `/questions/{id}` | 查看版本详情或软归档题目 |
| GET / POST | `/questions/{id}/versions` | 查询历史或创建不可变新版本 |
| POST | `/questions/{id}/versions/{version_id}/restore` | 基于历史内容创建新的恢复版本 |
| GET / POST | `/questions/{id}/shares` | 查询共享对象或按用户名授予只读使用权 |
| DELETE | `/questions/{id}/shares/{user_id}` | 撤销未来使用权，不删除已有问卷快照 |
| GET | `/questions/{id}/usages` | 查询使用该逻辑题目的问卷及版本 |
| GET | `/questions/{id}/statistics` | 跨问卷匿名统计，可用 `version_id` 筛选 |

题目版本只包含标题、题型、选项和校验约束；`required` 与跳转规则属于问卷实例。修改题型必须创建新题目。共享用户可使用所有版本，但不能修改原题；修改共享题目内容时，问卷编辑器会另存为自己的题目。

## 自定义题库与问卷选题

| 方法 | 路径 | 说明 |
|---|---|---|
| POST / GET | `/question-banks` | 创建或查询自己的题库 |
| GET / PATCH / DELETE | `/question-banks/{id}` | 题库详情、修改和删除 |
| POST | `/question-banks/{id}/items` | 加入个人或共享题目，并指定默认版本 |
| PATCH / DELETE | `/question-banks/{id}/items/{question_id}` | 更新推荐版本或移出题库 |
| POST | `/surveys/{id}/questions/from-library` | 将指定题目版本加入草稿问卷 |
| PUT | `/surveys/{id}/questions/{instance_id}/version` | 显式切换草稿中的题目版本 |

跨问卷统计按版本分别返回。数字题额外返回所有可见版本的总体平均值、最小值、最大值和直方图；文本题只返回匿名数量，不跨问卷暴露原始文本。题目所有者可以查看所有使用该题目的匿名汇总，共享用户只统计自己拥有的问卷。

交互调试以运行中的 Swagger `http://127.0.0.1:8000/docs` 为准。
