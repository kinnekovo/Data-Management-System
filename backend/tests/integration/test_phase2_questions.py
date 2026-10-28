from uuid import uuid4

from tests.integration.conftest import register_and_login


def create_library_question(api, headers, title="你的年龄"):
    response = api.post(
        "/api/v1/questions",
        headers=headers,
        json={
            "type": "number",
            "title": title,
            "options": [],
            "validation": {"min_value": 0, "max_value": 120, "integer_only": True},
            "change_note": "初始版本",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_survey(api, headers, title):
    response = api.post(
        "/api/v1/surveys",
        headers=headers,
        json={
            "title": title,
            "description": "第二阶段测试",
            "allow_anonymous": False,
            "allow_multiple_submissions": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_library_versions_sharing_banks_usage_and_cross_survey_stats(api):
    suffix = uuid4().hex[:8]
    owner_name = f"phase2_owner_{suffix}"
    teammate_name = f"phase2_team_{suffix}"
    respondent_name = f"phase2_fill_{suffix}"
    owner = register_and_login(api, owner_name)
    teammate = register_and_login(api, teammate_name)
    respondent = register_and_login(api, respondent_name)

    question = create_library_question(api, owner)
    question_id = question["id"]
    v1_id = question["current_version_id"]

    shared = api.post(
        f"/api/v1/questions/{question_id}/shares",
        headers=owner,
        json={"username": teammate_name},
    )
    assert shared.status_code == 201, shared.text
    shared_list = api.get("/api/v1/questions?scope=shared", headers=teammate).json()
    assert [item["id"] for item in shared_list["items"]] == [question_id]

    version = api.post(
        f"/api/v1/questions/{question_id}/versions",
        headers=owner,
        json={
            "type": "number",
            "title": "你的周岁年龄",
            "options": [],
            "validation": {"min_value": 0, "max_value": 120, "integer_only": True},
            "parent_version_id": v1_id,
            "change_note": "明确为周岁",
        },
    )
    assert version.status_code == 201, version.text
    v2 = version.json()
    assert v2["version_no"] == 2
    history = api.get(f"/api/v1/questions/{question_id}", headers=owner).json()
    assert [item["version_no"] for item in history["versions"]] == [2, 1]

    restored = api.post(
        f"/api/v1/questions/{question_id}/versions/{v1_id}/restore", headers=owner
    )
    assert restored.status_code == 201, restored.text
    assert restored.json()["version_no"] == 3
    assert restored.json()["parent_version_id"] == v1_id

    bank = api.post(
        "/api/v1/question-banks",
        headers=owner,
        json={"name": "人口学", "description": "常用人口学题目"},
    ).json()
    added = api.post(
        f"/api/v1/question-banks/{bank['id']}/items",
        headers=owner,
        json={"question_id": question_id, "default_version_id": v2["id"]},
    )
    assert added.status_code == 201, added.text
    bank_detail = api.get(f"/api/v1/question-banks/{bank['id']}", headers=owner).json()
    assert bank_detail["items"][0]["default_version"]["id"] == v2["id"]

    first_survey = create_survey(api, owner, "年龄调查 A")
    first_question = api.post(
        f"/api/v1/surveys/{first_survey['id']}/questions/from-library",
        headers=owner,
        json={"question_id": question_id, "question_version_id": v1_id, "required": True},
    ).json()
    second_survey = create_survey(api, teammate, "年龄调查 B")
    second_question = api.post(
        f"/api/v1/surveys/{second_survey['id']}/questions/from-library",
        headers=teammate,
        json={"question_id": question_id, "question_version_id": v2["id"], "required": True},
    ).json()
    assert first_question["version_no"] == 1
    assert second_question["version_no"] == 2

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

    usages = api.get(f"/api/v1/questions/{question_id}/usages", headers=owner).json()
    assert usages["total"] == 2
    stats = api.get(f"/api/v1/questions/{question_id}/statistics", headers=owner).json()
    assert stats["survey_count"] == 2
    assert stats["answered_count"] == 2
    assert stats["overall_number"]["average"] == 30
    assert {item["version_no"] for item in stats["version_stats"]} == {1, 2}

    teammate_stats = api.get(
        f"/api/v1/questions/{question_id}/statistics", headers=teammate
    ).json()
    assert teammate_stats["survey_count"] == 1
    assert teammate_stats["answered_count"] == 1

    revoke = api.delete(
        f"/api/v1/questions/{question_id}/shares/{shared.json()['user_id']}", headers=owner
    )
    assert revoke.status_code == 204
    assert api.get(f"/api/v1/questions/{question_id}", headers=teammate).status_code == 404
    assert api.get(
        f"/api/v1/surveys/{second_survey['id']}", headers=teammate
    ).json()["questions"][0]["title"] == "你的周岁年龄"


def test_editing_survey_question_creates_version_without_touching_published_snapshot(api):
    suffix = uuid4().hex[:8]
    owner = register_and_login(api, f"phase2_edit_{suffix}")
    respondent = register_and_login(api, f"phase2_answer_{suffix}")
    question = create_library_question(api, owner, "年龄")

    old_survey = create_survey(api, owner, "旧问卷")
    old_instance = api.post(
        f"/api/v1/surveys/{old_survey['id']}/questions/from-library",
        headers=owner,
        json={"question_id": question["id"], "required": True},
    ).json()
    published = api.post(f"/api/v1/surveys/{old_survey['id']}/publish", headers=owner).json()

    draft_survey = create_survey(api, owner, "新问卷")
    draft_instance = api.post(
        f"/api/v1/surveys/{draft_survey['id']}/questions/from-library",
        headers=owner,
        json={"question_id": question["id"], "required": True},
    ).json()
    changed = {**draft_instance, "title": "你的周岁年龄"}
    updated = api.patch(
        f"/api/v1/surveys/{draft_survey['id']}/questions/{draft_instance['id']}",
        headers=owner,
        json=changed,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["version_no"] == 2

    old_public = api.get(
        f"/api/v1/public/surveys/{published['slug']}", headers=respondent
    ).json()
    assert old_public["questions"][0]["title"] == "年龄"
    assert old_public["questions"][0]["question_version_id"] == old_instance["question_version_id"]
