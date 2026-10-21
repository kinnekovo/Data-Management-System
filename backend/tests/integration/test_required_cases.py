"""课程验收要求中的六个核心业务 API 测试。

这些测试使用 integration/conftest.py 创建的随机临时 MongoDB 数据库，
验证完成后由 session fixture 删除该测试数据库。
"""

from uuid import uuid4

from tests.integration.conftest import register_and_login


def unique_name(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


def create_survey(api, headers, **overrides):
    payload = {
        "title": "课程满意度调查",
        "description": "核心流程自动测试",
        "allow_anonymous": False,
        "allow_multiple_submissions": False,
        "expires_at": None,
    }
    payload.update(overrides)
    return api.post("/api/v1/surveys", headers=headers, json=payload)


def add_text_question(api, headers, survey_id, *, title="改进建议", required=True):
    return api.post(
        f"/api/v1/surveys/{survey_id}/questions",
        headers=headers,
        json={
            "type": "text",
            "title": title,
            "required": required,
            "options": [],
            "validation": {"min_length": 2, "max_length": 100},
            "rules": [],
        },
    )


def test_case_create_survey(api):
    """TC-A01：登录用户可以创建草稿问卷。"""
    owner = register_and_login(api, unique_name("create_owner"))

    response = create_survey(api, owner)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["title"] == "课程满意度调查"
    assert body["status"] == "draft"
    assert body["question_count"] == 0
    assert body["share_path"].startswith("/survey/")


def test_case_add_question(api):
    """TC-A02：创建者可以向草稿添加题目，后端生成稳定题目/选项 ID。"""
    owner = register_and_login(api, unique_name("question_owner"))
    survey = create_survey(api, owner).json()

    response = api.post(
        f"/api/v1/surveys/{survey['id']}/questions",
        headers=owner,
        json={
            "type": "single_choice",
            "title": "你是否满意？",
            "required": True,
            "options": [{"label": "满意"}, {"label": "不满意"}],
            "validation": {},
            "rules": [],
        },
    )

    assert response.status_code == 201, response.text
    question = response.json()
    assert question["id"]
    assert question["type"] == "single_choice"
    assert [item["label"] for item in question["options"]] == ["满意", "不满意"]
    assert all(item["id"] for item in question["options"])


def test_case_jump_logic(api):
    """TC-A03：命中单选跳转规则时跳过中间题，只接受实际路径答案。"""
    owner = register_and_login(api, unique_name("jump_owner"))
    respondent = register_and_login(api, unique_name("jump_fill"))
    survey = create_survey(api, owner).json()

    first = api.post(
        f"/api/v1/surveys/{survey['id']}/questions",
        headers=owner,
        json={
            "type": "single_choice",
            "title": "是否跳过说明题？",
            "required": True,
            "options": [{"label": "跳过"}, {"label": "继续"}],
            "validation": {},
            "rules": [],
        },
    ).json()
    middle = add_text_question(api, owner, survey["id"], title="说明原因").json()
    last = add_text_question(api, owner, survey["id"], title="最终建议").json()
    first["rules"] = [{
        "priority": 1,
        "operator": "eq",
        "value": first["options"][0]["id"],
        "target_question_id": last["id"],
    }]
    updated = api.patch(
        f"/api/v1/surveys/{survey['id']}/questions/{first['id']}",
        headers=owner,
        json=first,
    )
    assert updated.status_code == 200, updated.text
    published = api.post(f"/api/v1/surveys/{survey['id']}/publish", headers=owner)
    assert published.status_code == 200, published.text

    response = api.post(
        f"/api/v1/public/surveys/{published.json()['slug']}/responses",
        headers=respondent,
        json={"answers": [
            {"question_id": first["id"], "value": first["options"][0]["id"]},
            {"question_id": last["id"], "value": "最终建议内容"},
        ]},
    )

    assert response.status_code == 201, response.text
    assert response.json()["visited_question_ids"] == [first["id"], last["id"]]
    assert middle["id"] not in response.json()["visited_question_ids"]


def test_case_answer_validation(api):
    """TC-A04：文本少于最小长度时拒绝提交并返回明确业务错误。"""
    owner = register_and_login(api, unique_name("validation_owner"))
    respondent = register_and_login(api, unique_name("validation_fill"))
    survey = create_survey(api, owner).json()
    question = add_text_question(api, owner, survey["id"]).json()
    published = api.post(f"/api/v1/surveys/{survey['id']}/publish", headers=owner).json()

    response = api.post(
        f"/api/v1/public/surveys/{published['slug']}/responses",
        headers=respondent,
        json={"answers": [{"question_id": question["id"], "value": "短"}]},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_ANSWER"
    assert "不能少于" in response.json()["message"]


def test_case_submit_survey(api):
    """TC-A05：合法答卷提交后可以由创建者从答卷列表读取。"""
    owner = register_and_login(api, unique_name("submit_owner"))
    respondent_name = unique_name("submit_fill")
    respondent = register_and_login(api, respondent_name)
    survey = create_survey(api, owner).json()
    question = add_text_question(api, owner, survey["id"]).json()
    published = api.post(f"/api/v1/surveys/{survey['id']}/publish", headers=owner).json()

    submitted = api.post(
        f"/api/v1/public/surveys/{published['slug']}/responses",
        headers=respondent,
        json={"answers": [{"question_id": question["id"], "value": "希望增加案例"}]},
    )

    assert submitted.status_code == 201, submitted.text
    assert submitted.json()["response_id"]
    responses = api.get(f"/api/v1/surveys/{survey['id']}/responses", headers=owner)
    assert responses.status_code == 200, responses.text
    assert responses.json()["total"] == 1
    assert responses.json()["items"][0]["respondent_username"] == respondent_name
    assert responses.json()["items"][0]["answers"][0]["value"] == "希望增加案例"


def test_case_statistics(api):
    """TC-A06：两份单选答卷生成正确的提交总数和选项计数。"""
    owner = register_and_login(api, unique_name("stats_owner"))
    first_respondent = register_and_login(api, unique_name("stats_fill_a"))
    second_respondent = register_and_login(api, unique_name("stats_fill_b"))
    survey = create_survey(api, owner).json()
    question = api.post(
        f"/api/v1/surveys/{survey['id']}/questions",
        headers=owner,
        json={
            "type": "single_choice",
            "title": "课程评价",
            "required": True,
            "options": [{"label": "满意"}, {"label": "不满意"}],
            "validation": {},
            "rules": [],
        },
    ).json()
    published = api.post(f"/api/v1/surveys/{survey['id']}/publish", headers=owner).json()
    for headers, option in zip(
        (first_respondent, second_respondent),
        question["options"],
        strict=True,
    ):
        response = api.post(
            f"/api/v1/public/surveys/{published['slug']}/responses",
            headers=headers,
            json={"answers": [{"question_id": question["id"], "value": option["id"]}]},
        )
        assert response.status_code == 201, response.text

    response = api.get(f"/api/v1/surveys/{survey['id']}/statistics", headers=owner)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["submission_count"] == 2
    item = body["question_stats"][0]
    assert item["answered_count"] == 2
    assert {option["label"]: option["count"] for option in item["options"]} == {
        "满意": 1,
        "不满意": 1,
    }
