import math
from collections import Counter, defaultdict
from typing import Annotated, Any, Literal
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Query, status
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.api.dependencies import CurrentUser, DatabaseDep
from app.core.errors import AppError
from app.repositories.questions import get_question, get_question_version
from app.repositories.surveys import parse_object_id
from app.schemas.common import iso_datetime, json_value, utc_now
from app.schemas.question import QuestionCreate, QuestionShareCreate, QuestionVersionCreate
from app.services.validation import validate_survey_definition

router = APIRouter(prefix="/questions", tags=["questions"])


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _content(payload: QuestionCreate | QuestionVersionCreate) -> dict[str, Any]:
    data = payload.model_dump(exclude={"parent_version_id", "change_note"})
    for option in data["options"]:
        if not option.get("id"):
            option["id"] = _new_id("opt")
    definition = {"id": "library_preview", "required": False, "rules": [], **data}
    issues = validate_survey_definition([definition])
    if issues:
        raise AppError(422, "INVALID_QUESTION_DEFINITION", "题目定义不合法", issues)
    return data


def version_view(version: dict) -> dict[str, Any]:
    return {
        "id": str(version["_id"]),
        "question_id": str(version["question_id"]),
        "version_no": version["version_no"],
        "parent_version_id": (
            str(version["parent_version_id"]) if version.get("parent_version_id") else None
        ),
        "created_by": str(version["created_by"]),
        "title": version["title"],
        "type": version["type"],
        "options": json_value(version.get("options", [])),
        "validation": json_value(version.get("validation", {})),
        "change_note": version.get("change_note", ""),
        "created_at": iso_datetime(version["created_at"]),
    }


def question_view(database, question: dict, *, user_id: ObjectId) -> dict[str, Any]:
    current = database.question_versions.find_one({"_id": question["current_version_id"]})
    if current is None:
        raise AppError(500, "QUESTION_VERSION_MISSING", "题目的当前版本不存在")
    shared = question["owner_id"] != user_id
    owner = database.users.find_one({"_id": question["owner_id"]}, {"username": 1})
    return {
        "id": str(question["_id"]),
        "owner_id": str(question["owner_id"]),
        "owner_username": owner.get("username") if owner else None,
        "current_version_id": str(question["current_version_id"]),
        "archived": question.get("archived", False),
        "access": "shared" if shared else "owner",
        "created_at": iso_datetime(question["created_at"]),
        "updated_at": iso_datetime(question["updated_at"]),
        "current_version": version_view(current),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_question(
    payload: QuestionCreate, database: DatabaseDep, current_user: CurrentUser
) -> dict:
    now = utc_now()
    question_id = ObjectId()
    version_id = ObjectId()
    content = _content(payload)
    version = {
        "_id": version_id,
        "question_id": question_id,
        "version_no": 1,
        "parent_version_id": None,
        "created_by": current_user["_id"],
        **content,
        "change_note": payload.change_note.strip(),
        "created_at": now,
    }
    question = {
        "_id": question_id,
        "owner_id": current_user["_id"],
        "current_version_id": version_id,
        "archived": False,
        "created_at": now,
        "updated_at": now,
    }
    database.question_versions.insert_one(version)
    try:
        database.questions.insert_one(question)
    except Exception:
        database.question_versions.delete_one({"_id": version_id})
        raise
    return question_view(database, question, user_id=current_user["_id"])


@router.get("")
def list_questions(
    database: DatabaseDep,
    current_user: CurrentUser,
    scope: Annotated[Literal["all", "mine", "shared"], Query()] = "all",
    search: Annotated[str, Query(max_length=100)] = "",
) -> dict:
    owned_ids: set[ObjectId] = set()
    shared_ids: set[ObjectId] = set()
    if scope in {"all", "mine"}:
        owned_ids = {
            item["_id"]
            for item in database.questions.find(
                {"owner_id": current_user["_id"], "archived": False}, {"_id": 1}
            )
        }
    if scope in {"all", "shared"}:
        shared_ids = {
            item["question_id"]
            for item in database.question_shares.find(
                {"grantee_user_id": current_user["_id"]}, {"question_id": 1}
            )
        }
    ids = owned_ids | shared_ids
    documents = list(database.questions.find({"_id": {"$in": list(ids)}, "archived": False}))
    result = [question_view(database, item, user_id=current_user["_id"]) for item in documents]
    needle = search.strip().casefold()
    if needle:
        result = [item for item in result if needle in item["current_version"]["title"].casefold()]
    result.sort(key=lambda item: item["updated_at"], reverse=True)
    return {"items": result}


@router.get("/{question_id}")
def question_detail(
    question_id: str, database: DatabaseDep, current_user: CurrentUser
) -> dict:
    question = get_question(database, question_id, current_user["_id"])
    result = question_view(database, question, user_id=current_user["_id"])
    result["versions"] = [
        version_view(item)
        for item in database.question_versions.find({"question_id": question["_id"]}).sort(
            "version_no", -1
        )
    ]
    return result


@router.get("/{question_id}/versions")
def list_versions(
    question_id: str, database: DatabaseDep, current_user: CurrentUser
) -> dict:
    question = get_question(database, question_id, current_user["_id"])
    return {
        "items": [
            version_view(item)
            for item in database.question_versions.find({"question_id": question["_id"]}).sort(
                "version_no", -1
            )
        ]
    }


@router.post("/{question_id}/versions", status_code=status.HTTP_201_CREATED)
def create_version(
    question_id: str,
    payload: QuestionVersionCreate,
    database: DatabaseDep,
    current_user: CurrentUser,
) -> dict:
    question = get_question(database, question_id, current_user["_id"], require_owner=True)
    current = database.question_versions.find_one({"_id": question["current_version_id"]})
    if current is None:
        raise AppError(409, "QUESTION_VERSION_MISSING", "当前题目版本不存在")
    content = _content(payload)
    if content["type"] != current["type"]:
        raise AppError(409, "QUESTION_TYPE_IMMUTABLE", "修改题型时请创建一个新的题目")
    parent = current
    if payload.parent_version_id:
        parent = get_question_version(database, question, payload.parent_version_id)
    for _ in range(3):
        latest = database.question_versions.find_one(
            {"question_id": question["_id"]}, sort=[("version_no", -1)]
        )
        version = {
            "_id": ObjectId(),
            "question_id": question["_id"],
            "version_no": (latest["version_no"] if latest else 0) + 1,
            "parent_version_id": parent["_id"],
            "created_by": current_user["_id"],
            **content,
            "change_note": payload.change_note.strip(),
            "created_at": utc_now(),
        }
        try:
            database.question_versions.insert_one(version)
            break
        except DuplicateKeyError:
            continue
    else:
        raise AppError(409, "VERSION_CONFLICT", "题目版本创建冲突，请重试")
    database.questions.update_one(
        {"_id": question["_id"]},
        {"$set": {"current_version_id": version["_id"], "updated_at": version["created_at"]}},
    )
    return version_view(version)


@router.post(
    "/{question_id}/versions/{version_id}/restore", status_code=status.HTTP_201_CREATED
)
def restore_version(
    question_id: str,
    version_id: str,
    database: DatabaseDep,
    current_user: CurrentUser,
) -> dict:
    question = get_question(database, question_id, current_user["_id"], require_owner=True)
    source = get_question_version(database, question, version_id)
    payload = QuestionVersionCreate(
        type=source["type"],
        title=source["title"],
        options=source.get("options", []),
        validation=source.get("validation", {}),
        parent_version_id=str(source["_id"]),
        change_note=f"从 v{source['version_no']} 恢复",
    )
    return create_version(question_id, payload, database, current_user)


@router.delete("/{question_id}", status_code=204)
def archive_question(
    question_id: str, database: DatabaseDep, current_user: CurrentUser
) -> None:
    question = get_question(database, question_id, current_user["_id"], require_owner=True)
    database.questions.update_one(
        {"_id": question["_id"]}, {"$set": {"archived": True, "updated_at": utc_now()}}
    )


@router.get("/{question_id}/shares")
def list_shares(
    question_id: str, database: DatabaseDep, current_user: CurrentUser
) -> dict:
    question = get_question(database, question_id, current_user["_id"], require_owner=True)
    shares = list(database.question_shares.find({"question_id": question["_id"]}))
    user_ids = [item["grantee_user_id"] for item in shares]
    names = {
        item["_id"]: item["username"]
        for item in database.users.find({"_id": {"$in": user_ids}}, {"username": 1})
    }
    return {
        "items": [
            {
                "user_id": str(item["grantee_user_id"]),
                "username": names.get(item["grantee_user_id"]),
                "permission": item["permission"],
                "created_at": iso_datetime(item["created_at"]),
            }
            for item in shares
        ]
    }


@router.post("/{question_id}/shares", status_code=status.HTTP_201_CREATED)
def share_question(
    question_id: str,
    payload: QuestionShareCreate,
    database: DatabaseDep,
    current_user: CurrentUser,
) -> dict:
    question = get_question(database, question_id, current_user["_id"], require_owner=True)
    grantee = database.users.find_one({"username": payload.username})
    if grantee is None:
        raise AppError(404, "USER_NOT_FOUND", "接收用户不存在")
    if grantee["_id"] == current_user["_id"]:
        raise AppError(409, "CANNOT_SHARE_WITH_SELF", "不能把题目共享给自己")
    document = {
        "question_id": question["_id"],
        "grantee_user_id": grantee["_id"],
        "shared_by": current_user["_id"],
        "permission": "use",
        "created_at": utc_now(),
    }
    try:
        database.question_shares.insert_one(document)
    except DuplicateKeyError:
        raise AppError(409, "QUESTION_ALREADY_SHARED", "题目已经共享给该用户") from None
    return {
        "user_id": str(grantee["_id"]),
        "username": grantee["username"],
        "permission": "use",
        "created_at": iso_datetime(document["created_at"]),
    }


@router.delete("/{question_id}/shares/{user_id}", status_code=204)
def revoke_share(
    question_id: str,
    user_id: str,
    database: DatabaseDep,
    current_user: CurrentUser,
) -> None:
    question = get_question(database, question_id, current_user["_id"], require_owner=True)
    database.question_shares.delete_one(
        {
            "question_id": question["_id"],
            "grantee_user_id": parse_object_id(user_id, "用户"),
        }
    )


@router.get("/{question_id}/usages")
def question_usages(
    question_id: str, database: DatabaseDep, current_user: CurrentUser
) -> dict:
    question = get_question(database, question_id, current_user["_id"])
    query: dict[str, Any] = {"questions.question_id": question["_id"]}
    if question["owner_id"] != current_user["_id"]:
        query["owner_id"] = current_user["_id"]
    surveys = database.surveys.find(query).sort("updated_at", -1)
    items = []
    for survey in surveys:
        for item in survey.get("questions", []):
            if item.get("question_id") == question["_id"]:
                items.append(
                    {
                        "survey_id": str(survey["_id"]),
                        "survey_title": survey["title"],
                        "survey_status": survey["status"],
                        "survey_question_id": item["id"],
                        "question_version_id": str(item["question_version_id"]),
                        "updated_at": iso_datetime(survey["updated_at"]),
                    }
                )
    return {"items": items, "total": len(items)}


def _histogram(values: list[float], bucket_count: int = 10) -> list[dict[str, Any]]:
    if not values:
        return []
    minimum, maximum = min(values), max(values)
    if minimum == maximum:
        return [{"from": minimum, "to": maximum, "count": len(values)}]
    width = (maximum - minimum) / bucket_count
    counts = [0] * bucket_count
    for value in values:
        index = min(bucket_count - 1, int((value - minimum) / width))
        counts[index] += 1
    return [
        {
            "from": round(minimum + index * width, 4),
            "to": round(minimum + (index + 1) * width, 4),
            "count": count,
        }
        for index, count in enumerate(counts)
    ]


@router.get("/{question_id}/statistics")
def cross_survey_statistics(
    question_id: str,
    database: DatabaseDep,
    current_user: CurrentUser,
    version_id: Annotated[str | None, Query()] = None,
) -> dict:
    question = get_question(database, question_id, current_user["_id"])
    match: dict[str, Any] = {"answers.library_question_id": question["_id"]}
    selected_version: ObjectId | None = None
    if version_id:
        selected_version = get_question_version(database, question, version_id)["_id"]
        match["answers.question_version_id"] = selected_version
    if question["owner_id"] != current_user["_id"]:
        owned_survey_ids = [
            item["_id"] for item in database.surveys.find({"owner_id": current_user["_id"]}, {"_id": 1})
        ]
        match["survey_id"] = {"$in": owned_survey_ids}
    pipeline = [
        {"$match": match},
        {"$unwind": "$answers"},
        {"$match": {"answers.library_question_id": question["_id"]}},
    ]
    if selected_version:
        pipeline.append({"$match": {"answers.question_version_id": selected_version}})
    pipeline.append(
        {
            "$project": {
                "_id": 0,
                "survey_id": 1,
                "version_id": "$answers.question_version_id",
                "value": "$answers.value",
            }
        }
    )
    answers = list(database.responses.aggregate(pipeline))
    version_ids = {item["version_id"] for item in answers if item.get("version_id")}
    versions = {
        item["_id"]: item
        for item in database.question_versions.find({"_id": {"$in": list(version_ids)}})
    }
    grouped: dict[ObjectId, list[Any]] = defaultdict(list)
    survey_ids: set[ObjectId] = set()
    for item in answers:
        if item.get("version_id"):
            grouped[item["version_id"]].append(item["value"])
        survey_ids.add(item["survey_id"])
    version_stats = []
    numeric_all: list[float] = []
    for item_version_id, values in grouped.items():
        definition = versions.get(item_version_id)
        if definition is None:
            continue
        base: dict[str, Any] = {
            "version_id": str(item_version_id),
            "version_no": definition["version_no"],
            "title": definition["title"],
            "type": definition["type"],
            "answered_count": len(values),
        }
        if definition["type"] in {"single_choice", "multiple_choice"}:
            flattened = [choice for value in values for choice in (value if isinstance(value, list) else [value])]
            counts = Counter(flattened)
            base["options"] = [
                {"id": option["id"], "label": option["label"], "count": counts[option["id"]]}
                for option in definition.get("options", [])
            ]
        elif definition["type"] == "number":
            numeric = [float(value) for value in values if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))]
            numeric_all.extend(numeric)
            base.update(
                {
                    "average": sum(numeric) / len(numeric) if numeric else None,
                    "minimum": min(numeric) if numeric else None,
                    "maximum": max(numeric) if numeric else None,
                    "histogram": _histogram(numeric),
                }
            )
        version_stats.append(base)
    version_stats.sort(key=lambda item: item["version_no"], reverse=True)
    result: dict[str, Any] = {
        "question_id": str(question["_id"]),
        "survey_count": len(survey_ids),
        "answered_count": len(answers),
        "privacy": "anonymous_aggregate",
        "version_stats": version_stats,
    }
    if numeric_all:
        result["overall_number"] = {
            "average": sum(numeric_all) / len(numeric_all),
            "minimum": min(numeric_all),
            "maximum": max(numeric_all),
            "histogram": _histogram(numeric_all),
        }
    return json_value(result)
