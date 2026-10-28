from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, status
from pymongo.errors import DuplicateKeyError

from app.api.dependencies import CurrentUser, DatabaseDep
from app.core.errors import AppError
from app.repositories.surveys import get_public_survey
from app.schemas.common import iso_datetime, json_value, utc_now
from app.schemas.response import SubmissionInput
from app.services.rule_engine import PathValidationError, replay_path

router = APIRouter(prefix="/public/surveys", tags=["public-surveys"])


def _is_expired(expires_at: datetime | None) -> bool:
    if expires_at is None:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= utc_now()


def _ensure_accepting(survey: dict) -> None:
    if survey["status"] == "draft":
        raise AppError(409, "SURVEY_NOT_PUBLISHED", "问卷尚未发布")
    if survey["status"] == "closed":
        raise AppError(409, "SURVEY_CLOSED", "问卷已关闭")
    if _is_expired(survey.get("expires_at")):
        raise AppError(409, "SURVEY_EXPIRED", "问卷已截止")


def public_view(survey: dict) -> dict[str, Any]:
    return {
        "slug": survey["slug"],
        "title": survey["title"],
        "description": survey.get("description", ""),
        "allow_anonymous": survey.get("allow_anonymous", False),
        "status": survey["status"],
        "expires_at": iso_datetime(survey.get("expires_at")),
        "definition_version": survey.get("definition_version", 1),
        "questions": json_value(survey.get("questions", [])),
    }


@router.get("/{slug}")
def get_public_definition(slug: str, database: DatabaseDep, _current_user: CurrentUser) -> dict:
    survey = get_public_survey(database, slug)
    _ensure_accepting(survey)
    return public_view(survey)


@router.post("/{slug}/responses", status_code=status.HTTP_201_CREATED)
def submit_response(
    slug: str,
    payload: SubmissionInput,
    database: DatabaseDep,
    current_user: CurrentUser,
) -> dict:
    survey = get_public_survey(database, slug)
    _ensure_accepting(survey)
    try:
        normalized_answers, visited = replay_path(
            survey.get("questions", []),
            [answer.model_dump() for answer in payload.answers],
        )
    except PathValidationError as error:
        raise AppError(422, error.code, error.message, error.details) from error

    question_map = {item["id"]: item for item in survey.get("questions", [])}
    enriched_answers = []
    for answer in normalized_answers:
        enriched = dict(answer)
        question = question_map.get(answer["question_id"], {})
        if question.get("question_id") and question.get("question_version_id"):
            enriched["library_question_id"] = question["question_id"]
            enriched["question_version_id"] = question["question_version_id"]
        enriched_answers.append(enriched)

    submitted_at = utc_now()
    document: dict[str, Any] = {
        "survey_id": survey["_id"],
        "respondent_id": current_user["_id"],
        "definition_version": survey.get("definition_version", 1),
        "answers": enriched_answers,
        "submitted_at": submitted_at,
    }
    if not survey.get("allow_multiple_submissions", False):
        document["submission_guard"] = f"{survey['_id']}:{current_user['_id']}"
    try:
        result = database.responses.insert_one(document)
    except DuplicateKeyError:
        raise AppError(409, "ALREADY_SUBMITTED", "你已经提交过这份问卷") from None
    return {
        "response_id": str(result.inserted_id),
        "submitted_at": iso_datetime(submitted_at),
        "visited_question_ids": visited,
    }
