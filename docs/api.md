# M1 API

基础路径：`/api/v1`。Swagger UI 位于 `/docs`。M1 只有以下两个接口。

## `GET /api/v1/health/live`

只表示 API 进程存活，不访问 MongoDB。

- `200 OK`: `{"status":"alive","service":"survey-system-api"}`

## `GET /api/v1/health/ready`

通过 PyMongo 对 MongoDB 执行真实 `ping`。同步路由由 FastAPI 在线程池执行，避免阻塞异步事件循环。

- `200 OK`: `{"status":"ready","database":"connected"}`
- `503 Service Unavailable`: `{"detail":"MongoDB unavailable"}`

失败响应不会暴露连接串、账号、密码或底层异常。注册、登录、问卷、题目、答卷和统计接口均未在 M1 创建。
