from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentUser, DatabaseDep, SettingsDep
from app.core.errors import AppError
from app.repositories.surveys import get_owned_survey
from app.schemas.common import iso_datetime, json_value
from app.services.statistics import question_summary, text_details

router = APIRouter(prefix="/surveys", tags=["statistics"])


@router.get("/{survey_id}/responses")
def list_responses(
    survey_id: str,
    database: DatabaseDep,
    current_user: CurrentUser,
    settings: SettingsDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1)] = 20,
) -> dict:
    page_size = min(page_size, settings.max_page_size)
    survey = get_owned_survey(database, survey_id, current_user["_id"])
    query = {"survey_id": survey["_id"]}
    total = database.responses.count_documents(query)
    cursor = (
        database.responses.find(query)
        .sort("submitted_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    documents = list(cursor)
    usernames: dict = {}
    if not survey.get("allow_anonymous", False):
        user_ids = {item["respondent_id"] for item in documents}
        usernames = {
            item["_id"]: item["username"]
            for item in database.users.find({"_id": {"$in": list(user_ids)}})
        }
    items = []
    for document in documents:
        item = {
            "id": str(document["_id"]),
            "definition_version": document["definition_version"],
            "answers": json_value(document["answers"]),
            "submitted_at": iso_datetime(document["submitted_at"]),
        }
        if not survey.get("allow_anonymous", False):
            item["respondent_id"] = str(document["respondent_id"])
            item["respondent_username"] = usernames.get(document["respondent_id"])
        items.append(item)
    return {"page": page, "page_size": page_size, "total": total, "items": items}


@router.get("/{survey_id}/statistics")
def survey_statistics(
    survey_id: str, database: DatabaseDep, current_user: CurrentUser
) -> dict:
    survey = get_owned_survey(database, survey_id, current_user["_id"])
    return {
        "survey_id": str(survey["_id"]),
        "title": survey["title"],
        "submission_count": database.responses.count_documents({"survey_id": survey["_id"]}),
        "question_stats": [
            json_value(question_summary(database, survey, question))
            for question in survey.get("questions", [])
        ],
    }


@router.get("/{survey_id}/statistics/questions/{question_id}")
def question_statistics(
    survey_id: str,
    question_id: str,
    database: DatabaseDep,
    current_user: CurrentUser,
    settings: SettingsDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1)] = 20,
) -> dict:
    page_size = min(page_size, settings.max_page_size)
    survey = get_owned_survey(database, survey_id, current_user["_id"])
    question = next(
        (item for item in survey.get("questions", []) if item["id"] == question_id), None
    )
    if question is None:
        raise AppError(404, "QUESTION_NOT_FOUND", "题目不存在")
    if question["type"] == "text":
        return json_value(text_details(database, survey, question, page, page_size))
    return json_value(question_summary(database, survey, question))
