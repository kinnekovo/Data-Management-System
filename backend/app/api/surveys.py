from datetime import UTC, datetime
from secrets import token_urlsafe
from typing import Any
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, status
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.api.dependencies import CurrentUser, DatabaseDep
from app.api.questions import create_question as create_library_question
from app.api.questions import create_version as create_library_version
from app.core.errors import AppError
from app.repositories.questions import get_question, get_question_version
from app.repositories.surveys import get_owned_survey
from app.schemas.common import iso_datetime, json_value, utc_now
from app.schemas.question import (
    LibraryQuestionUse,
    QuestionCreate,
    QuestionVersionCreate,
    SurveyQuestionVersionSwitch,
)
from app.schemas.survey import QuestionInput, QuestionOrderUpdate, SurveyCreate, SurveyUpdate
from app.services.validation import validate_survey_definition

router = APIRouter(prefix="/surveys", tags=["surveys"])


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def survey_view(document: dict, include_questions: bool = True) -> dict[str, Any]:
    result = {
        "id": str(document["_id"]),
        "slug": document["slug"],
        "title": document["title"],
        "description": document.get("description", ""),
        "allow_anonymous": document.get("allow_anonymous", False),
        "allow_multiple_submissions": document.get("allow_multiple_submissions", False),
        "status": document["status"],
        "expires_at": iso_datetime(document.get("expires_at")),
        "question_count": len(document.get("questions", [])),
        "schema_version": document.get("schema_version", 1),
        "definition_version": document.get("definition_version", 1),
        "created_at": iso_datetime(document["created_at"]),
        "updated_at": iso_datetime(document["updated_at"]),
        "published_at": iso_datetime(document.get("published_at")),
        "closed_at": iso_datetime(document.get("closed_at")),
        "share_path": f"/survey/{document['slug']}",
    }
    if include_questions:
        result["questions"] = json_value(document.get("questions", []))
    return result


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _question_from_version(
    version: dict,
    *,
    required: bool = False,
    rules: list[dict[str, Any]] | None = None,
    instance_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": instance_id or _new_id("q"),
        "question_id": version["question_id"],
        "question_version_id": version["_id"],
        "version_no": version["version_no"],
        "type": version["type"],
        "title": version["title"],
        "required": required,
        "options": version.get("options", []),
        "validation": version.get("validation", {}),
        "rules": rules or [],
    }


def _create_library_definition(
    payload: QuestionInput, database, current_user: dict, *, change_note: str
) -> tuple[dict, dict]:
    created = create_library_question(
        QuestionCreate(
            type=payload.type,
            title=payload.title,
            options=payload.options,
            validation=payload.validation,
            change_note=change_note,
        ),
        database,
        current_user,
    )
    question = database.questions.find_one({"_id": ObjectId(created["id"])})
    version = database.question_versions.find_one({"_id": question["current_version_id"]})
    return question, version


def _updated_question(payload: QuestionInput, question_id: str) -> dict[str, Any]:
    data = payload.model_dump()
    data["id"] = question_id
    for option in data["options"]:
        if not option.get("id"):
            option["id"] = _new_id("opt")
    return data


@router.post("", status_code=status.HTTP_201_CREATED)
def create_survey(payload: SurveyCreate, database: DatabaseDep, current_user: CurrentUser) -> dict:
    now = utc_now()
    base = {
        "owner_id": current_user["_id"],
        "title": payload.title,
        "description": payload.description,
        "allow_anonymous": payload.allow_anonymous,
        "allow_multiple_submissions": payload.allow_multiple_submissions,
        "status": "draft",
        "expires_at": _utc(payload.expires_at),
        "questions": [],
        "schema_version": 2,
        "definition_version": 1,
        "created_at": now,
        "updated_at": now,
        "published_at": None,
        "closed_at": None,
    }
    for _ in range(5):
        base["slug"] = token_urlsafe(12).replace("_", "").replace("-", "")
        try:
            result = database.surveys.insert_one(base)
            base["_id"] = result.inserted_id
            return survey_view(base)
        except DuplicateKeyError:
            continue
    raise AppError(503, "SLUG_GENERATION_FAILED", "暂时无法生成问卷链接，请重试")


@router.get("")
def list_surveys(database: DatabaseDep, current_user: CurrentUser) -> dict:
    items = database.surveys.find({"owner_id": current_user["_id"]}).sort("created_at", -1)
    return {"items": [survey_view(item, include_questions=False) for item in items]}


@router.get("/{survey_id}")
def get_survey(survey_id: str, database: DatabaseDep, current_user: CurrentUser) -> dict:
    return survey_view(get_owned_survey(database, survey_id, current_user["_id"]))


@router.patch("/{survey_id}")
def update_survey(
    survey_id: str,
    payload: SurveyUpdate,
    database: DatabaseDep,
    current_user: CurrentUser,
) -> dict:
    survey = get_owned_survey(database, survey_id, current_user["_id"])
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return survey_view(survey)
    if survey["status"] == "closed":
        raise AppError(409, "SURVEY_CLOSED", "已关闭问卷不能再修改")
    if survey["status"] == "published" and set(changes) != {"expires_at"}:
        raise AppError(409, "SURVEY_FROZEN", "发布后仅可修改截止时间或关闭问卷")
    if "expires_at" in changes:
        changes["expires_at"] = _utc(changes["expires_at"])
    changes["updated_at"] = utc_now()
    updated = database.surveys.find_one_and_update(
        {"_id": survey["_id"]}, {"$set": changes}, return_document=ReturnDocument.AFTER
    )
    return survey_view(updated)


@router.post("/{survey_id}/questions", status_code=status.HTTP_201_CREATED)
def add_question(
    survey_id: str,
    payload: QuestionInput,
    database: DatabaseDep,
    current_user: CurrentUser,
) -> dict:
    survey = get_owned_survey(database, survey_id, current_user["_id"])
    if survey["status"] != "draft":
        raise AppError(409, "SURVEY_FROZEN", "只有草稿问卷可以编辑题目")
    _library_question, version = _create_library_definition(
        payload, database, current_user, change_note="在问卷中创建题目"
    )
    question = _question_from_version(
        version, required=payload.required, rules=[item.model_dump() for item in payload.rules]
    )
    database.surveys.update_one(
        {"_id": survey["_id"]},
        {"$push": {"questions": question}, "$set": {"updated_at": utc_now()}},
    )
    return json_value(question)


@router.patch("/{survey_id}/questions/{question_id}")
def update_question(
    survey_id: str,
    question_id: str,
    payload: QuestionInput,
    database: DatabaseDep,
    current_user: CurrentUser,
) -> dict:
    survey = get_owned_survey(database, survey_id, current_user["_id"])
    if survey["status"] != "draft":
        raise AppError(409, "SURVEY_FROZEN", "只有草稿问卷可以编辑题目")
    existing = next(
        (item for item in survey.get("questions", []) if item["id"] == question_id), None
    )
    if existing is None:
        raise AppError(404, "QUESTION_NOT_FOUND", "题目不存在")
    content_fields = ("type", "title", "options", "validation")
    incoming = payload.model_dump()
    content_changed = any(incoming[field] != existing.get(field) for field in content_fields)
    library_question = None
    version = None
    if existing.get("question_id") and existing.get("question_version_id"):
        library_question = database.questions.find_one({"_id": existing["question_id"]})
        version = database.question_versions.find_one({"_id": existing["question_version_id"]})

    if library_question is None or version is None:
        library_question, version = _create_library_definition(
            payload, database, current_user, change_note="迁移旧问卷题目"
        )
        content_changed = False
    elif content_changed:
        if library_question["owner_id"] != current_user["_id"] or payload.type != version["type"]:
            library_question, version = _create_library_definition(
                payload,
                database,
                current_user,
                change_note="基于已有题目另存为新题目",
            )
        else:
            created = create_library_version(
                str(library_question["_id"]),
                QuestionVersionCreate(
                    type=payload.type,
                    title=payload.title,
                    options=payload.options,
                    validation=payload.validation,
                    parent_version_id=str(version["_id"]),
                    change_note="从问卷编辑器创建新版本",
                ),
                database,
                current_user,
            )
            version = database.question_versions.find_one({"_id": ObjectId(created["id"])})

    question = _question_from_version(
        version,
        required=payload.required,
        rules=[item.model_dump() for item in payload.rules],
        instance_id=question_id,
    )
    result = database.surveys.update_one(
        {"_id": survey["_id"], "questions.id": question_id},
        {"$set": {"questions.$": question, "updated_at": utc_now()}},
    )
    if result.matched_count == 0:
        raise AppError(404, "QUESTION_NOT_FOUND", "题目不存在")
    return json_value(question)


@router.post("/{survey_id}/questions/from-library", status_code=status.HTTP_201_CREATED)
def add_question_from_library(
    survey_id: str,
    payload: LibraryQuestionUse,
    database: DatabaseDep,
    current_user: CurrentUser,
) -> dict:
    survey = get_owned_survey(database, survey_id, current_user["_id"])
    if survey["status"] != "draft":
        raise AppError(409, "SURVEY_FROZEN", "只有草稿问卷可以添加题目")
    library_question = get_question(database, payload.question_id, current_user["_id"])
    version = (
        get_question_version(database, library_question, payload.question_version_id)
        if payload.question_version_id
        else database.question_versions.find_one(
            {"_id": library_question["current_version_id"]}
        )
    )
    question = _question_from_version(version, required=payload.required)
    database.surveys.update_one(
        {"_id": survey["_id"]},
        {"$push": {"questions": question}, "$set": {"updated_at": utc_now()}},
    )
    return json_value(question)


@router.put("/{survey_id}/questions/{question_id}/version")
def switch_question_version(
    survey_id: str,
    question_id: str,
    payload: SurveyQuestionVersionSwitch,
    database: DatabaseDep,
    current_user: CurrentUser,
) -> dict:
    survey = get_owned_survey(database, survey_id, current_user["_id"])
    if survey["status"] != "draft":
        raise AppError(409, "SURVEY_FROZEN", "只有草稿问卷可以切换题目版本")
    existing = next(
        (item for item in survey.get("questions", []) if item["id"] == question_id), None
    )
    if existing is None or not existing.get("question_id"):
        raise AppError(404, "QUESTION_NOT_FOUND", "题目不存在或尚未迁移")
    library_question = get_question(
        database, str(existing["question_id"]), current_user["_id"]
    )
    version = get_question_version(database, library_question, payload.question_version_id)
    switched = _question_from_version(
        version,
        required=existing.get("required", False),
        rules=existing.get("rules", []),
        instance_id=question_id,
    )
    database.surveys.update_one(
        {"_id": survey["_id"], "questions.id": question_id},
        {"$set": {"questions.$": switched, "updated_at": utc_now()}},
    )
    return json_value(switched)


@router.delete("/{survey_id}/questions/{question_id}", status_code=204)
def delete_question(
    survey_id: str,
    question_id: str,
    database: DatabaseDep,
    current_user: CurrentUser,
) -> None:
    survey = get_owned_survey(database, survey_id, current_user["_id"])
    if survey["status"] != "draft":
        raise AppError(409, "SURVEY_FROZEN", "只有草稿问卷可以编辑题目")
    if not any(item["id"] == question_id for item in survey.get("questions", [])):
        raise AppError(404, "QUESTION_NOT_FOUND", "题目不存在")
    sources = [
        item["id"]
        for item in survey.get("questions", [])
        if any(rule.get("target_question_id") == question_id for rule in item.get("rules", []))
    ]
    if sources:
        raise AppError(
            409,
            "QUESTION_REFERENCED",
            "题目正被跳转规则引用，请先删除相关规则",
            {"source_question_ids": sources},
        )
    database.surveys.update_one(
        {"_id": survey["_id"]},
        {"$pull": {"questions": {"id": question_id}}, "$set": {"updated_at": utc_now()}},
    )


@router.put("/{survey_id}/question-order")
def reorder_questions(
    survey_id: str,
    payload: QuestionOrderUpdate,
    database: DatabaseDep,
    current_user: CurrentUser,
) -> dict:
    survey = get_owned_survey(database, survey_id, current_user["_id"])
    if survey["status"] != "draft":
        raise AppError(409, "SURVEY_FROZEN", "只有草稿问卷可以调整题序")
    current = {item["id"]: item for item in survey.get("questions", [])}
    if len(payload.question_ids) != len(set(payload.question_ids)) or set(payload.question_ids) != set(current):
        raise AppError(422, "INVALID_QUESTION_ORDER", "题序必须且只能包含问卷中的全部题目 ID")
    reordered = [current[item] for item in payload.question_ids]
    issues = validate_survey_definition(reordered)
    rule_issues = [item for item in issues if item["field"].startswith("rules")]
    if rule_issues:
        raise AppError(422, "INVALID_RULE_ORDER", "调整题序会使跳转规则失效", rule_issues)
    database.surveys.update_one(
        {"_id": survey["_id"]},
        {"$set": {"questions": reordered, "updated_at": utc_now()}},
    )
    return {"questions": json_value(reordered)}


@router.post("/{survey_id}/publish")
def publish_survey(survey_id: str, database: DatabaseDep, current_user: CurrentUser) -> dict:
    survey = get_owned_survey(database, survey_id, current_user["_id"])
    if survey["status"] != "draft":
        raise AppError(409, "INVALID_SURVEY_STATE", "只有草稿问卷可以发布")
    issues = validate_survey_definition(survey.get("questions", []))
    if issues:
        raise AppError(422, "INVALID_SURVEY_DEFINITION", "问卷定义不符合发布要求", issues)
    now = utc_now()
    updated = database.surveys.find_one_and_update(
        {"_id": survey["_id"], "status": "draft"},
        {"$set": {"status": "published", "published_at": now, "updated_at": now}},
        return_document=ReturnDocument.AFTER,
    )
    if updated is None:
        raise AppError(409, "SURVEY_STATE_CHANGED", "问卷状态已变化，请刷新后重试")
    return survey_view(updated)


@router.post("/{survey_id}/close")
def close_survey(survey_id: str, database: DatabaseDep, current_user: CurrentUser) -> dict:
    survey = get_owned_survey(database, survey_id, current_user["_id"])
    if survey["status"] != "published":
        raise AppError(409, "INVALID_SURVEY_STATE", "只有已发布问卷可以关闭")
    now = utc_now()
    updated = database.surveys.find_one_and_update(
        {"_id": survey["_id"], "status": "published"},
        {"$set": {"status": "closed", "closed_at": now, "updated_at": now}},
        return_document=ReturnDocument.AFTER,
    )
    if updated is None:
        raise AppError(409, "SURVEY_STATE_CHANGED", "问卷状态已变化，请刷新后重试")
    return survey_view(updated)
