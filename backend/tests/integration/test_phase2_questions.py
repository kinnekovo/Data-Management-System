"""Phase-two acceptance tests mapped to the eight changed requirements."""

from uuid import uuid4

from tests.integration.conftest import register_and_login


def unique_name(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


def create_question(api, headers, *, title="你的年龄", question_type="number"):
    choice = question_type in {"single_choice", "multiple_choice"}
    response = api.post(
        "/api/v1/questions",
        headers=headers,
        json={
            "type": question_type,
            "title": title,
            "options": [{"label": "是"}, {"label": "否"}] if choice else [],
            "validation": (
                {"min_value": 0, "max_value": 120, "integer_only": True}
                if question_type == "number"
                else {}
            ),
            "change_note": "初始版本",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_version(api, headers, question, *, title="你的周岁年龄"):
    current = question["current_version"]
    response = api.post(
        f"/api/v1/questions/{question['id']}/versions",
        headers=headers,
        json={
            "type": current["type"],
            "title": title,
            "options": current["options"],
            "validation": current["validation"],
            "parent_version_id": current["id"],
            "change_note": "创建第二版本",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_survey(api, headers, title, *, multiple=True):
    response = api.post(
        "/api/v1/surveys",
        headers=headers,
        json={
            "title": title,
            "description": "第二阶段自动测试",
            "allow_anonymous": False,
            "allow_multiple_submissions": multiple,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def add_from_library(api, headers, survey, question, version_id=None, *, required=True):
    response = api.post(
        f"/api/v1/surveys/{survey['id']}/questions/from-library",
        headers=headers,
        json={
            "question_id": question["id"],
            "question_version_id": version_id,
            "required": required,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_requirement_1_save_and_reuse_question(api):
    owner = register_and_login(api, unique_name("reuse_owner"))
    question = create_question(api, owner)
    assert question["current_version"]["validation"] == {
        "min_value": 0,
        "max_value": 120,
        "integer_only": True,
    }
    first_survey = create_survey(api, owner, "复用问卷 A")
    second_survey = create_survey(api, owner, "复用问卷 B")
    first = add_from_library(api, owner, first_survey, question)
    second = add_from_library(api, owner, second_survey, question)

    assert first["question_id"] == second["question_id"] == question["id"]
    assert first["question_version_id"] == second["question_version_id"]
    assert first["id"] != second["id"]
    listed = api.get("/api/v1/questions?scope=mine", headers=owner).json()["items"]
    assert any(item["id"] == question["id"] for item in listed)


def test_requirement_2_share_question_for_reuse(api):
    owner = register_and_login(api, unique_name("share_owner"))
    teammate_name = unique_name("share_team")
    teammate = register_and_login(api, teammate_name)
    question = create_question(api, owner, title="共享题目")

    shared = api.post(
        f"/api/v1/questions/{question['id']}/shares",
        headers=owner,
        json={"username": teammate_name},
    )
    assert shared.status_code == 201, shared.text
    shared_items = api.get("/api/v1/questions?scope=shared", headers=teammate).json()["items"]
    assert [item["id"] for item in shared_items] == [question["id"]]

    teammate_survey = create_survey(api, teammate, "同事问卷")
    instance = add_from_library(api, teammate, teammate_survey, question)
    assert instance["question_id"] == question["id"]
    assert api.delete(
        f"/api/v1/questions/{question['id']}/shares/{shared.json()['user_id']}",
        headers=owner,
    ).status_code == 204
    assert api.get(f"/api/v1/questions/{question['id']}", headers=teammate).status_code == 404
    snapshot = api.get(
        f"/api/v1/surveys/{teammate_survey['id']}", headers=teammate
    ).json()["questions"][0]
    assert snapshot["title"] == "共享题目"


def test_requirement_3_edit_does_not_change_published_survey(api):
    owner = register_and_login(api, unique_name("freeze_owner"))
    respondent = register_and_login(api, unique_name("freeze_fill"))
    question = create_question(api, owner, title="年龄")
    old_survey = create_survey(api, owner, "去年问卷")
    old_instance = add_from_library(api, owner, old_survey, question)
    published = api.post(
        f"/api/v1/surveys/{old_survey['id']}/publish", headers=owner
    ).json()

    draft_survey = create_survey(api, owner, "今年问卷")
    draft_instance = add_from_library(api, owner, draft_survey, question)
    updated = api.patch(
        f"/api/v1/surveys/{draft_survey['id']}/questions/{draft_instance['id']}",
        headers=owner,
        json={**draft_instance, "title": "你的周岁年龄"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["version_no"] == 2

    public_snapshot = api.get(
        f"/api/v1/public/surveys/{published['slug']}", headers=respondent
    ).json()["questions"][0]
    assert public_snapshot["title"] == "年龄"
    assert public_snapshot["question_version_id"] == old_instance["question_version_id"]
    switch = api.put(
        f"/api/v1/surveys/{old_survey['id']}/questions/{old_instance['id']}/version",
        headers=owner,
        json={"question_version_id": updated.json()["question_version_id"]},
    )
    assert switch.status_code == 409
    assert switch.json()["code"] == "SURVEY_FROZEN"


def test_requirement_4_version_history_and_restore(api):
    owner = register_and_login(api, unique_name("history_owner"))
    question = create_question(api, owner, title="题目 v1")
    v1_id = question["current_version_id"]
    v2 = create_version(api, owner, question, title="题目 v2")
    restored = api.post(
        f"/api/v1/questions/{question['id']}/versions/{v1_id}/restore", headers=owner
    )

    assert restored.status_code == 201, restored.text
    assert restored.json()["version_no"] == 3
    assert restored.json()["parent_version_id"] == v1_id
    assert restored.json()["title"] == "题目 v1"
    history = api.get(f"/api/v1/questions/{question['id']}", headers=owner).json()
    assert [item["version_no"] for item in history["versions"]] == [3, 2, 1]
    assert v2["parent_version_id"] == v1_id


def test_requirement_5_different_versions_coexist(api):
    owner = register_and_login(api, unique_name("versions_owner"))
    question = create_question(api, owner, title="旧题")
    v1_id = question["current_version_id"]
    v2 = create_version(api, owner, question, title="新题")
    old_survey = create_survey(api, owner, "使用旧版")
    new_survey = create_survey(api, owner, "使用新版")
    old_instance = add_from_library(api, owner, old_survey, question, v1_id)
    new_instance = add_from_library(api, owner, new_survey, question, v2["id"])

    assert old_instance["version_no"] == 1
    assert old_instance["title"] == "旧题"
    assert new_instance["version_no"] == 2
    assert new_instance["title"] == "新题"
    assert old_instance["question_id"] == new_instance["question_id"]


def test_requirement_6_list_question_usages(api):
    owner = register_and_login(api, unique_name("usage_owner"))
    question = create_question(api, owner, title="使用情况题")
    draft_survey = create_survey(api, owner, "草稿使用")
    published_survey = create_survey(api, owner, "发布使用")
    add_from_library(api, owner, draft_survey, question)
    add_from_library(api, owner, published_survey, question)
    assert api.post(
        f"/api/v1/surveys/{published_survey['id']}/publish", headers=owner
    ).status_code == 200

    usages = api.get(f"/api/v1/questions/{question['id']}/usages", headers=owner)
    assert usages.status_code == 200, usages.text
    assert usages.json()["total"] == 2
    assert {item["survey_title"] for item in usages.json()["items"]} == {
        "草稿使用",
        "发布使用",
    }
    assert {item["survey_status"] for item in usages.json()["items"]} == {
        "draft",
        "published",
    }


def test_requirement_7_question_bank_and_default_version_update(api):
    owner = register_and_login(api, unique_name("bank_owner"))
    question = create_question(api, owner, title="题库题目")
    v1_id = question["current_version_id"]
    v2 = create_version(api, owner, question, title="题库题目新版")
    bank = api.post(
        "/api/v1/question-banks",
        headers=owner,
        json={"name": "常用题库", "description": "第二阶段测试"},
    ).json()
    added = api.post(
        f"/api/v1/question-banks/{bank['id']}/items",
        headers=owner,
        json={"question_id": question["id"], "default_version_id": v1_id},
    )
    assert added.status_code == 201, added.text
    assert added.json()["default_version"]["version_no"] == 1

    updated = api.patch(
        f"/api/v1/question-banks/{bank['id']}/items/{question['id']}",
        headers=owner,
        json={"default_version_id": v2["id"]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["default_version"]["version_no"] == 2
    detail = api.get(f"/api/v1/question-banks/{bank['id']}", headers=owner).json()
    assert detail["item_count"] == 1
    assert detail["items"][0]["default_version"]["id"] == v2["id"]


def test_requirement_8_cross_survey_question_statistics(api):
    owner = register_and_login(api, unique_name("stats_owner"))
    teammate_name = unique_name("stats_team")
    teammate = register_and_login(api, teammate_name)
    respondent = register_and_login(api, unique_name("stats_fill"))
    question = create_question(api, owner, title="你的年龄")
    v1_id = question["current_version_id"]
    v2 = create_version(api, owner, question, title="你的周岁年龄")
    assert api.post(
        f"/api/v1/questions/{question['id']}/shares",
        headers=owner,
        json={"username": teammate_name},
    ).status_code == 201

    first_survey = create_survey(api, owner, "年龄问卷 A")
    second_survey = create_survey(api, teammate, "年龄问卷 B")
    first_question = add_from_library(api, owner, first_survey, question, v1_id)
    second_question = add_from_library(api, teammate, second_survey, question, v2["id"])
    first_published = api.post(
        f"/api/v1/surveys/{first_survey['id']}/publish", headers=owner
    ).json()
    second_published = api.post(
        f"/api/v1/surveys/{second_survey['id']}/publish", headers=teammate
    ).json()
    assert api.post(
        f"/api/v1/public/surveys/{first_published['slug']}/responses",
        headers=respondent,
        json={"answers": [{"question_id": first_question["id"], "value": 20}]},
    ).status_code == 201
    assert api.post(
        f"/api/v1/public/surveys/{second_published['slug']}/responses",
        headers=respondent,
        json={"answers": [{"question_id": second_question["id"], "value": 40}]},
    ).status_code == 201

    owner_stats = api.get(
        f"/api/v1/questions/{question['id']}/statistics", headers=owner
    ).json()
    assert owner_stats["survey_count"] == 2
    assert owner_stats["answered_count"] == 2
    assert owner_stats["overall_number"]["average"] == 30
    assert owner_stats["overall_number"]["minimum"] == 20
    assert owner_stats["overall_number"]["maximum"] == 40
    assert sum(item["count"] for item in owner_stats["overall_number"]["histogram"]) == 2
    assert {item["version_no"] for item in owner_stats["version_stats"]} == {1, 2}

    teammate_stats = api.get(
        f"/api/v1/questions/{question['id']}/statistics", headers=teammate
    ).json()
    assert teammate_stats["survey_count"] == 1
    assert teammate_stats["answered_count"] == 1
    assert teammate_stats["overall_number"]["average"] == 40
