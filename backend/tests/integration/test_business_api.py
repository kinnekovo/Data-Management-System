from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt

from tests.integration.conftest import register_and_login


def create_survey(api, headers, **overrides):
    payload = {
        "title": "集成测试问卷",
        "description": "四题型与跳转",
        "allow_anonymous": False,
        "allow_multiple_submissions": False,
    }
    payload.update(overrides)
    response = api.post("/api/v1/surveys", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def add_question(api, headers, survey_id, payload):
    response = api.post(f"/api/v1/surveys/{survey_id}/questions", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def text_question(title="说明", required=False):
    return {
        "type": "text",
        "title": title,
        "required": required,
        "options": [],
        "validation": {"min_length": 2, "max_length": 40},
        "rules": [],
    }


def test_authentication_and_owner_isolation(api_context):
    api, _app, settings = api_context
    suffix = uuid4().hex[:8]
    owner_name = f"owner_{suffix}"
    other_name = f"other_{suffix}"
    owner = register_and_login(api, owner_name)
    other = register_and_login(api, other_name)

    duplicate = api.post(
        "/api/v1/auth/register",
        json={"username": owner_name, "password": "SecurePass123"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "USERNAME_EXISTS"
    wrong = api.post(
        "/api/v1/auth/login", json={"username": owner_name, "password": "WrongPass123"}
    )
    assert wrong.status_code == 401
    assert api.get("/api/v1/auth/me").status_code == 401
    assert api.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401

    expired = jwt.encode(
        {"sub": "000000000000000000000001", "exp": datetime.now(UTC) - timedelta(seconds=1)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    assert api.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401

    survey = create_survey(api, owner)
    assert api.get(f"/api/v1/surveys/{survey['id']}", headers=other).status_code == 404
    assert api.get(f"/api/v1/surveys/{survey['id']}/statistics", headers=other).status_code == 404
    assert len(api.get("/api/v1/surveys", headers=owner).json()["items"]) >= 1
    assert all(item["id"] != survey["id"] for item in api.get("/api/v1/surveys", headers=other).json()["items"])


def test_question_crud_definition_rules_submission_and_statistics(api):
    suffix = uuid4().hex[:8]
    owner_name = f"creator_{suffix}"
    respondent_name = f"fill_{suffix}"
    second_name = f"fill2_{suffix}"
    owner = register_and_login(api, owner_name)
    respondent = register_and_login(api, respondent_name)
    second = register_and_login(api, second_name)

    empty = create_survey(api, owner, title="空问卷")
    invalid_publish = api.post(f"/api/v1/surveys/{empty['id']}/publish", headers=owner)
    assert invalid_publish.status_code == 422
    assert invalid_publish.json()["code"] == "INVALID_SURVEY_DEFINITION"

    survey = create_survey(api, owner, allow_multiple_submissions=True)
    draft_public = api.get(f"/api/v1/public/surveys/{survey['slug']}", headers=respondent)
    assert draft_public.status_code == 409
    assert draft_public.json()["code"] == "SURVEY_NOT_PUBLISHED"
    draft_update = api.patch(
        f"/api/v1/surveys/{survey['id']}",
        headers=owner,
        json={"description": "已更新的草稿说明"},
    )
    assert draft_update.status_code == 200
    assert draft_update.json()["description"] == "已更新的草稿说明"
    q1 = add_question(
        api,
        owner,
        survey["id"],
        {
            "type": "single_choice",
            "title": "是否跳过文本题",
            "required": True,
            "options": [{"label": "跳过"}, {"label": "继续"}],
            "validation": {},
            "rules": [],
        },
    )
    q2 = add_question(api, owner, survey["id"], text_question("路径文本", required=True))
    q3 = add_question(
        api,
        owner,
        survey["id"],
        {
            "type": "multiple_choice",
            "title": "选择标签",
            "required": True,
            "options": [{"label": "A"}, {"label": "B"}, {"label": "C"}],
            "validation": {"min_selections": 1, "max_selections": 2},
            "rules": [],
        },
    )
    q4 = add_question(
        api,
        owner,
        survey["id"],
        {
            "type": "number",
            "title": "评分",
            "required": True,
            "options": [],
            "validation": {"min_value": 0, "max_value": 100, "integer_only": True},
            "rules": [],
        },
    )
    q1["rules"] = [
        {
            "priority": 1,
            "operator": "eq",
            "value": q1["options"][0]["id"],
            "target_question_id": q3["id"],
        }
    ]
    updated = api.patch(
        f"/api/v1/surveys/{survey['id']}/questions/{q1['id']}", headers=owner, json=q1
    )
    assert updated.status_code == 200, updated.text

    referenced_delete = api.delete(
        f"/api/v1/surveys/{survey['id']}/questions/{q3['id']}", headers=owner
    )
    assert referenced_delete.status_code == 409
    backwards_order = api.put(
        f"/api/v1/surveys/{survey['id']}/question-order",
        headers=owner,
        json={"question_ids": [q3["id"], q1["id"], q2["id"], q4["id"]]},
    )
    assert backwards_order.status_code == 422

    publish = api.post(f"/api/v1/surveys/{survey['id']}/publish", headers=owner)
    assert publish.status_code == 200, publish.text
    slug = publish.json()["slug"]
    frozen = api.patch(
        f"/api/v1/surveys/{survey['id']}", headers=owner, json={"title": "不允许"}
    )
    assert frozen.status_code == 409

    public = api.get(f"/api/v1/public/surveys/{slug}", headers=respondent)
    assert public.status_code == 200
    assert "owner_id" not in public.json()
    assert api.get(f"/api/v1/public/surveys/{slug}").status_code == 401

    empty_stats = api.get(f"/api/v1/surveys/{survey['id']}/statistics", headers=owner).json()
    empty_by_id = {item["question_id"]: item for item in empty_stats["question_stats"]}
    assert empty_stats["submission_count"] == 0
    assert empty_by_id[q4["id"]]["average"] is None
    assert empty_by_id[q4["id"]]["answered_count"] == 0
    assert all(item["count"] == 0 for item in empty_by_id[q1["id"]]["options"])

    skip_answers = {
        "answers": [
            {"question_id": q1["id"], "value": q1["options"][0]["id"]},
            {"question_id": q3["id"], "value": [q3["options"][0]["id"], q3["options"][1]["id"]]},
            {"question_id": q4["id"], "value": 20},
        ]
    }
    first_submit = api.post(
        f"/api/v1/public/surveys/{slug}/responses", headers=respondent, json=skip_answers
    )
    assert first_submit.status_code == 201, first_submit.text
    assert first_submit.json()["visited_question_ids"] == [q1["id"], q3["id"], q4["id"]]

    forged = {"answers": skip_answers["answers"] + [{"question_id": q2["id"], "value": "伪造路径"}]}
    assert api.post(
        f"/api/v1/public/surveys/{slug}/responses", headers=respondent, json=forged
    ).status_code == 422
    invalid_number = {"answers": [
        {"question_id": q1["id"], "value": q1["options"][0]["id"]},
        {"question_id": q3["id"], "value": [q3["options"][0]["id"]]},
        {"question_id": q4["id"], "value": "20"},
    ]}
    assert api.post(
        f"/api/v1/public/surveys/{slug}/responses", headers=second, json=invalid_number
    ).status_code == 422

    sequential_answers = {"answers": [
        {"question_id": q1["id"], "value": q1["options"][1]["id"]},
        {"question_id": q2["id"], "value": "有效文本"},
        {"question_id": q3["id"], "value": [q3["options"][1]["id"]]},
        {"question_id": q4["id"], "value": 40},
    ]}
    assert api.post(
        f"/api/v1/public/surveys/{slug}/responses", headers=second, json=sequential_answers
    ).status_code == 201

    stats = api.get(f"/api/v1/surveys/{survey['id']}/statistics", headers=owner)
    assert stats.status_code == 200
    body = stats.json()
    assert body["submission_count"] == 2
    by_id = {item["question_id"]: item for item in body["question_stats"]}
    assert by_id[q2["id"]]["answered_count"] == 1
    assert by_id[q4["id"]]["average"] == 30
    multi_counts = {item["id"]: item["count"] for item in by_id[q3["id"]]["options"]}
    assert multi_counts[q3["options"][0]["id"]] == 1
    assert multi_counts[q3["options"][1]["id"]] == 2
    text_detail = api.get(
        f"/api/v1/surveys/{survey['id']}/statistics/questions/{q2['id']}?page=1&page_size=1",
        headers=owner,
    ).json()
    assert text_detail["total"] == 1
    assert text_detail["items"][0]["value"] == "有效文本"
    responses = api.get(f"/api/v1/surveys/{survey['id']}/responses", headers=owner).json()
    assert responses["total"] == 2
    assert all("respondent_username" in item for item in responses["items"])

    close = api.post(f"/api/v1/surveys/{survey['id']}/close", headers=owner)
    assert close.status_code == 200
    assert api.post(
        f"/api/v1/public/surveys/{slug}/responses", headers=second, json=sequential_answers
    ).status_code == 409


def test_anonymous_identity_duplicate_policy_and_concurrent_guard(api, api_context):
    _client, app, _settings = api_context
    suffix = uuid4().hex[:8]
    owner = register_and_login(api, f"anon_owner_{suffix}")
    respondent = register_and_login(api, f"anon_fill_{suffix}")
    survey = create_survey(api, owner, title="匿名问卷", allow_anonymous=True)
    q1 = add_question(api, owner, survey["id"], text_question(required=True))
    publish = api.post(f"/api/v1/surveys/{survey['id']}/publish", headers=owner).json()
    payload = {"answers": [{"question_id": q1["id"], "value": "匿名内容"}]}

    def submit_once():
        return api.post(
            f"/api/v1/public/surveys/{publish['slug']}/responses",
            headers=respondent,
            json=payload,
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = sorted(pool.map(lambda _: submit_once(), range(2)))
    assert statuses == [201, 409]

    items = api.get(f"/api/v1/surveys/{survey['id']}/responses", headers=owner).json()["items"]
    assert len(items) == 1
    assert "respondent_id" not in items[0]
    assert "respondent_username" not in items[0]

    database = app.state.mongodb_database
    stored = database.responses.find_one({"survey_id": database.surveys.find_one({"slug": publish["slug"]})["_id"]})
    assert stored["respondent_id"] is not None
    assert isinstance(stored["submission_guard"], str)

    expired = create_survey(
        api,
        owner,
        title="已截止问卷",
        expires_at=(datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
    )
    expired_q = add_question(api, owner, expired["id"], text_question(required=True))
    expired_published = api.post(f"/api/v1/surveys/{expired['id']}/publish", headers=owner).json()
    expired_submit = api.post(
        f"/api/v1/public/surveys/{expired_published['slug']}/responses",
        headers=respondent,
        json={"answers": [{"question_id": expired_q["id"], "value": "过期"}]},
    )
    assert expired_submit.status_code == 409
    assert expired_submit.json()["code"] == "SURVEY_EXPIRED"


def test_draft_question_reorder_delete_and_repeat_allowed(api):
    suffix = uuid4().hex[:8]
    owner = register_and_login(api, f"crud_owner_{suffix}")
    respondent = register_and_login(api, f"repeat_fill_{suffix}")
    survey = create_survey(api, owner, title="题目管理", allow_multiple_submissions=True)
    first = add_question(api, owner, survey["id"], text_question("第一题", required=True))
    second = add_question(api, owner, survey["id"], text_question("第二题"))

    reordered = api.put(
        f"/api/v1/surveys/{survey['id']}/question-order",
        headers=owner,
        json={"question_ids": [second["id"], first["id"]]},
    )
    assert reordered.status_code == 200, reordered.text
    assert [item["id"] for item in reordered.json()["questions"]] == [second["id"], first["id"]]

    deleted = api.delete(
        f"/api/v1/surveys/{survey['id']}/questions/{second['id']}", headers=owner
    )
    assert deleted.status_code == 204
    detail = api.get(f"/api/v1/surveys/{survey['id']}", headers=owner).json()
    assert [item["id"] for item in detail["questions"]] == [first["id"]]

    published = api.post(f"/api/v1/surveys/{survey['id']}/publish", headers=owner).json()
    payload = {"answers": [{"question_id": first["id"], "value": "重复提交"}]}
    first_submit = api.post(
        f"/api/v1/public/surveys/{published['slug']}/responses",
        headers=respondent,
        json=payload,
    )
    second_submit = api.post(
        f"/api/v1/public/surveys/{published['slug']}/responses",
        headers=respondent,
        json=payload,
    )
    assert first_submit.status_code == second_submit.status_code == 201
    responses = api.get(f"/api/v1/surveys/{survey['id']}/responses", headers=owner).json()
    assert responses["total"] == 2
